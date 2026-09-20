//! Browser-local player with separate validated local file operations.
//! Separate from the deliberately narrow, ROM-free peer checkpoint experiment.
use crate::{snapshot, *};

struct LocalPlayer {
    deck: ControlDeck,
    saved: Option<(Vec<u8>, bool)>,
    rom_sha256: [u8; 32],
    core_sha256: Option<[u8; 32]>,
    state_codec: Option<Result<crate::local_state::Codec, String>>,
    history: Option<crate::rewind::History>,
}
thread_local! {
    static PLAYER: RefCell<Option<LocalPlayer>> = const { RefCell::new(None) };
    static OUTPUT: RefCell<Vec<u8>> = const { RefCell::new(Vec::new()) };
}
fn result(value: Result<(), String>) -> u32 {
    match value {
        Ok(()) => 1,
        Err(message) => {
            OUTPUT.with_borrow_mut(|output| *output = message.into_bytes());
            0
        }
    }
}
fn load(rom: &[u8]) -> Result<LocalPlayer, String> {
    let mut deck = ControlDeck::with_config(
        Config::default()
            .with_sram_dir(None)
            .with_ram_state(RamState::AllZeros)
            .with_filter(tetanes_core::video::VideoFilter::Pixellate)
            .with_region(NesRegion::Auto),
    );
    deck.load_rom("local-game", &mut std::io::Cursor::new(rom))
        .map_err(|error| error.to_string())?;
    deck.set_sample_rate(48_000.0);
    use sha2::{Digest, Sha256};
    Ok(LocalPlayer {
        deck,
        saved: None,
        rom_sha256: Sha256::digest(rom).into(),
        core_sha256: None,
        state_codec: None,
        history: None,
    })
}
#[unsafe(no_mangle)]
pub extern "C" fn local_alloc(len: usize) -> *mut u8 {
    let bytes = vec![0u8; len].into_boxed_slice();
    Box::into_raw(bytes) as *mut u8
}
/// # Safety
/// Pointer and length must describe the allocation returned by local_alloc, used once.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn local_initialize(ptr: *mut u8, len: usize) -> u32 {
    let rom = unsafe { Box::from_raw(std::ptr::slice_from_raw_parts_mut(ptr, len)) };
    result(load(&rom).map(|player| PLAYER.with_borrow_mut(|slot| *slot = Some(player))))
}
#[unsafe(no_mangle)]
pub extern "C" fn local_frame(one: u8, two: u8) -> u32 {
    result(PLAYER.with_borrow_mut(|slot| {
        let player = slot.as_mut().ok_or("No game loaded")?;
        clock_inputs(&mut player.deck, one, two)
    }))
}
pub(crate) fn clock_inputs(deck: &mut ControlDeck, one: u8, two: u8) -> Result<(), String> {
    for (port, mask) in [(Player::One, one), (Player::Two, two)] {
        for (index, button) in [
            JoypadBtnState::A,
            JoypadBtnState::B,
            JoypadBtnState::SELECT,
            JoypadBtnState::START,
            JoypadBtnState::UP,
            JoypadBtnState::DOWN,
            JoypadBtnState::LEFT,
            JoypadBtnState::RIGHT,
        ]
        .iter()
        .enumerate()
        {
            deck.bus_mut()
                .input
                .joypad_mut(port)
                .set_button(*button, mask & (1 << index) != 0);
        }
    }
    deck.clock_frame()
        .map(|_| ())
        .map_err(|error| error.to_string())
}
#[unsafe(no_mangle)]
pub extern "C" fn local_save() -> u32 {
    result(PLAYER.with_borrow_mut(|slot| {
        let player = slot.as_mut().ok_or("No game loaded")?;
        player.saved = Some((snapshot(&player.deck), player.deck.bus().cpu.corrupted));
        Ok(())
    }))
}
#[unsafe(no_mangle)]
pub extern "C" fn local_restore() -> u32 {
    result(PLAYER.with_borrow_mut(|slot| {
        let player = slot.as_mut().ok_or("No game loaded")?;
        let (bytes, corrupted) = player.saved.as_ref().ok_or("No save in this tab")?;
        player
            .deck
            .deserialize_state(bytes)
            .map_err(|error| error.to_string())?;
        player.deck.bus_mut().cpu.corrupted = *corrupted;
        player.history = None;
        Ok(())
    }))
}
/// The Rust format owns the limit; the worker queries it before copying imports.
#[unsafe(no_mangle)]
pub extern "C" fn local_battery_limit() -> usize {
    crate::local_file::LIMIT
}
/// Bounded allocation shared by local file imports and the fixed core identity.
/// A zero pointer means rejection; no allocation occurs for invalid lengths.
fn allocate_file(len: usize) -> *mut u8 {
    if len == 0 || len > crate::local_file::LIMIT {
        return std::ptr::null_mut();
    }
    local_alloc(len)
}
#[unsafe(no_mangle)]
pub extern "C" fn local_battery_alloc(len: usize) -> *mut u8 {
    allocate_file(len)
}
/// Bind the trusted worker's actual WASM digest once per loaded cartridge.
/// # Safety
/// Pointer/length must describe a live local_battery_alloc allocation, consumed once.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn local_bind_core(ptr: *mut u8, len: usize) -> u32 {
    let bytes = unsafe { Box::from_raw(std::ptr::slice_from_raw_parts_mut(ptr, len)) };
    result(PLAYER.with_borrow_mut(|slot| {
        let player = slot.as_mut().ok_or("No game loaded")?;
        let hash: [u8; 32] = bytes
            .as_ref()
            .try_into()
            .map_err(|_| "Invalid core identity")?;
        if player.core_sha256.is_some() {
            return Err("Core identity already bound".into());
        }
        player.core_sha256 = Some(hash);
        Ok(())
    }))
}
#[unsafe(no_mangle)]
pub extern "C" fn local_has_battery() -> u32 {
    PLAYER.with_borrow(|slot| {
        u32::from(
            slot.as_ref()
                .is_some_and(|player| player.deck.cart_battery_backed() == Some(true)),
        )
    })
}
#[unsafe(no_mangle)]
pub extern "C" fn local_battery_info() -> u32 {
    result(PLAYER.with_borrow(|slot| {
        let player = slot.as_ref().ok_or("No game loaded")?;
        let core = player
            .core_sha256
            .as_ref()
            .ok_or("Core identity not bound")?;
        let battery = crate::battery::Battery::new(&player.deck, &player.rom_sha256, core)?;
        OUTPUT.with_borrow_mut(|output| *output = serde_json::to_vec(&battery.info()).unwrap());
        Ok(())
    }))
}
#[unsafe(no_mangle)]
pub extern "C" fn local_battery_export() -> u32 {
    result(PLAYER.with_borrow(|slot| {
        let player = slot.as_ref().ok_or("No game loaded")?;
        let core = player
            .core_sha256
            .as_ref()
            .ok_or("Core identity not bound")?;
        let battery = crate::battery::Battery::new(&player.deck, &player.rom_sha256, core)?;
        OUTPUT.with_borrow_mut(|output| *output = battery.export(&player.deck));
        Ok(())
    }))
}
/// # Safety
/// Pointer/length must describe a live local_battery_alloc allocation, consumed once.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn local_battery_import(ptr: *mut u8, len: usize) -> u32 {
    let bytes = unsafe { Box::from_raw(std::ptr::slice_from_raw_parts_mut(ptr, len)) };
    result(PLAYER.with_borrow_mut(|slot| {
        let player = slot.as_mut().ok_or("No game loaded")?;
        let core = player
            .core_sha256
            .as_ref()
            .ok_or("Core identity not bound")?;
        let battery = crate::battery::Battery::new(&player.deck, &player.rom_sha256, core)?;
        battery.restore(&mut player.deck, &bytes)?;
        player.history = None;
        Ok(())
    }))
}
// Build only on a save operation, never as a condition for loading/playing a ROM.
fn prepare_state(player: &mut LocalPlayer) -> Result<(), String> {
    if player.state_codec.is_none() {
        let core = player
            .core_sha256
            .as_ref()
            .ok_or("Core identity not bound")?;
        player.state_codec = Some(crate::local_state::Codec::new(
            &player.deck,
            &player.rom_sha256,
            core,
        ));
    }
    Ok(())
}
/// Shared budget; separate accessor preserves the established battery ABI.
#[unsafe(no_mangle)]
pub extern "C" fn local_state_limit() -> usize {
    crate::local_file::LIMIT
}
#[unsafe(no_mangle)]
pub extern "C" fn local_state_alloc(len: usize) -> *mut u8 {
    allocate_file(len)
}
#[unsafe(no_mangle)]
pub extern "C" fn local_state_info() -> u32 {
    result(PLAYER.with_borrow_mut(|slot| {
        let player = slot.as_mut().ok_or("No game loaded")?;
        prepare_state(player)?;
        let codec = player
            .state_codec
            .as_ref()
            .unwrap()
            .as_ref()
            .map_err(Clone::clone)?;
        OUTPUT.with_borrow_mut(|output| *output = serde_json::to_vec(&codec.info()).unwrap());
        Ok(())
    }))
}
/// # Safety
/// Pointer/length must describe a live local_state_alloc allocation, consumed once.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn local_state_validate(ptr: *mut u8, len: usize) -> u32 {
    let bytes = unsafe { Box::from_raw(std::ptr::slice_from_raw_parts_mut(ptr, len)) };
    result(PLAYER.with_borrow_mut(|slot| {
        let player = slot.as_mut().ok_or("No game loaded")?;
        prepare_state(player)?;
        player
            .state_codec
            .as_ref()
            .unwrap()
            .as_ref()
            .map_err(Clone::clone)?
            .validate_file(&bytes)
    }))
}
#[unsafe(no_mangle)]
pub extern "C" fn local_state_export() -> u32 {
    result(PLAYER.with_borrow_mut(|slot| {
        let player = slot.as_mut().ok_or("No game loaded")?;
        prepare_state(player)?;
        let codec = player
            .state_codec
            .as_ref()
            .ok_or("Core identity not bound")?
            .as_ref()
            .map_err(Clone::clone)?;
        let bytes = codec.export(&player.deck)?;
        OUTPUT.with_borrow_mut(|output| *output = bytes);
        Ok(())
    }))
}
/// # Safety
/// Pointer/length must describe a live local_state_alloc allocation, consumed once.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn local_state_import(ptr: *mut u8, len: usize) -> u32 {
    let bytes = unsafe { Box::from_raw(std::ptr::slice_from_raw_parts_mut(ptr, len)) };
    result(PLAYER.with_borrow_mut(|slot| {
        let player = slot.as_mut().ok_or("No game loaded")?;
        prepare_state(player)?;
        let codec = player
            .state_codec
            .as_ref()
            .ok_or("Core identity not bound")?
            .as_ref()
            .map_err(Clone::clone)?;
        codec.restore(&mut player.deck, &bytes)?;
        player.history = None;
        Ok(())
    }))
}
#[unsafe(no_mangle)]
pub extern "C" fn local_rewind_clear() {
    PLAYER.with_borrow_mut(|slot| {
        if let Some(player) = slot {
            player.history = None;
        }
    });
}
#[unsafe(no_mangle)]
pub extern "C" fn local_rewind_record(one: u8, two: u8) -> u32 {
    result(PLAYER.with_borrow_mut(|slot| {
        let player = slot.as_mut().ok_or("No game loaded")?;
        prepare_state(player)?;
        let codec = player
            .state_codec
            .as_ref()
            .unwrap()
            .as_ref()
            .map_err(Clone::clone)?;
        let history = player
            .history
            .get_or_insert_with(|| crate::rewind::History::new(&player.deck));
        if let Err(error) = history.record(&mut player.deck, codec, one, two) {
            player.history = None;
            return Err(error);
        }
        Ok(())
    }))
}
#[unsafe(no_mangle)]
pub extern "C" fn local_rewind_info() -> u32 {
    result(PLAYER.with_borrow(|slot| {
        let player = slot.as_ref().ok_or("No game loaded")?;
        let info = player.history.as_ref().map_or_else(
            || {
                let mut info = crate::rewind::History::new(&player.deck).info();
                info["retainedBytes"] = 0.into();
                info
            },
            |history| history.info(),
        );
        OUTPUT.with_borrow_mut(|output| *output = serde_json::to_vec(&info).unwrap());
        Ok(())
    }))
}
#[unsafe(no_mangle)]
pub extern "C" fn local_rewind(seconds: f64) -> u32 {
    result(PLAYER.with_borrow_mut(|slot| {
        let player = slot.as_mut().ok_or("No game loaded")?;
        prepare_state(player)?;
        let codec = player
            .state_codec
            .as_ref()
            .unwrap()
            .as_ref()
            .map_err(Clone::clone)?;
        let history = player.history.as_mut().ok_or("No rewind history yet")?;
        let pixels = history.rewind(&mut player.deck, codec, seconds)?;
        OUTPUT.with_borrow_mut(|output| *output = pixels);
        Ok(())
    }))
}
#[unsafe(no_mangle)]
pub extern "C" fn local_fps() -> f64 {
    PLAYER.with_borrow(|slot| match slot.as_ref().unwrap().deck.region() {
        NesRegion::Pal | NesRegion::Dendy => 50.0,
        _ => 60.0,
    })
}
// Pixels, PCM, error text and validated local files only; no upstream snapshots.
#[unsafe(no_mangle)]
pub extern "C" fn local_output(kind: u32) -> *const u8 {
    OUTPUT.with_borrow_mut(|output| {
        PLAYER.with_borrow_mut(|slot| {
            if let Some(player) = slot {
                match kind {
                    5 => *output = player.deck.frame_buffer().to_vec(),
                    2 => {
                        *output = player
                            .deck
                            .audio_samples()
                            .iter()
                            .flat_map(|sample| sample.to_le_bytes())
                            .collect()
                    }
                    _ => {}
                }
            }
        });
        output.as_ptr()
    })
}
#[unsafe(no_mangle)]
pub extern "C" fn local_output_len() -> usize {
    OUTPUT.with_borrow(|output| output.len())
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn battery_abi_bounds_binding_and_failure_preserve_loaded_game() {
        let mut rom = std::fs::read("fixture.local.nes").unwrap();
        rom[6] |= 2;
        PLAYER.with_borrow_mut(|slot| *slot = Some(load(&rom).unwrap()));
        assert!(local_battery_alloc(0).is_null());
        assert_eq!(local_battery_limit(), crate::local_file::LIMIT);
        assert!(local_battery_alloc(local_battery_limit() + 1).is_null());
        unsafe {
            let ptr = local_battery_alloc(local_battery_limit());
            assert!(!ptr.is_null(), "exact limit allocation is allowed");
            assert_eq!(
                local_battery_import(ptr, local_battery_limit()),
                0,
                "size allowance does not bypass file validation"
            );
        }
        assert_eq!(local_has_battery(), 1);
        assert_eq!(
            local_battery_info(),
            0,
            "metadata also requires actual core binding"
        );
        assert_eq!(local_battery_export(), 0, "must bind actual core first");
        unsafe {
            let ptr = local_battery_alloc(31);
            assert_eq!(local_bind_core(ptr, 31), 0);
            let ptr = local_battery_alloc(32);
            assert_eq!(local_bind_core(ptr, 32), 1);
            let ptr = local_battery_alloc(32);
            assert_eq!(local_bind_core(ptr, 32), 0, "cannot rebind identity");
        }
        assert_eq!(local_battery_info(), 1);
        let info: serde_json::Value =
            OUTPUT.with_borrow(|bytes| serde_json::from_slice(bytes).unwrap());
        assert_eq!(info["limit"], crate::local_file::LIMIT);
        assert_eq!(info["identity"].as_str().unwrap().len(), 64);
        assert_eq!(local_battery_export(), 1);
        let bytes = OUTPUT.with_borrow(Clone::clone);
        let before = PLAYER.with_borrow(|slot| canonical(&slot.as_ref().unwrap().deck));
        unsafe {
            let ptr = local_battery_alloc(bytes.len());
            std::ptr::copy_nonoverlapping(bytes.as_ptr(), ptr, bytes.len());
            *ptr ^= 1;
            assert_eq!(local_battery_import(ptr, bytes.len()), 0);
        }
        assert_eq!(
            before,
            PLAYER.with_borrow(|slot| canonical(&slot.as_ref().unwrap().deck))
        );
        assert_eq!(local_frame(0, 0), 1);
        assert_eq!(
            local_battery_export(),
            1,
            "failed import leaves worker usable"
        );
    }
    #[test]
    fn non_nrom_local_save_replay_and_errors() {
        let original = std::fs::read("fixture.local.nes").unwrap();
        // The original diagnostic never switches banks; replicate its PRG in both
        // windows to exercise real mapper loading/state without third-party ROMs.
        for mapper in [0, 1, 2, 3, 4, 7] {
            let mut rom = original.clone();
            if mapper != 0 {
                rom[4] = 2;
                rom.splice(
                    16 + 16384..16 + 16384,
                    original[16..16 + 16384].iter().copied(),
                );
            }
            rom[6] = mapper << 4;
            let ptr = local_alloc(rom.len());
            unsafe {
                std::ptr::copy_nonoverlapping(rom.as_ptr(), ptr, rom.len());
                assert_eq!(local_initialize(ptr, rom.len()), 1);
            }
            for _ in 0..20 {
                assert_eq!(local_frame(0, 0), 1);
            }
            assert_eq!(local_save(), 1);
            for _ in 0..10 {
                assert_eq!(local_frame(64, 0), 1);
            }
            let expected = PLAYER.with_borrow(|slot| canonical(&slot.as_ref().unwrap().deck));
            assert_eq!(local_restore(), 1);
            for _ in 0..10 {
                assert_eq!(local_frame(64, 0), 1);
            }
            assert_eq!(
                expected,
                PLAYER.with_borrow(|slot| canonical(&slot.as_ref().unwrap().deck)),
                "mapper {mapper}"
            );
        }
        assert!(load(b"invalid").is_err());
    }
}
