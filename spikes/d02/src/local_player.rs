//! Browser-local player. Its in-memory saves never cross the WASM boundary.
//! Separate from the deliberately narrow, ROM-free peer checkpoint experiment.
use crate::{snapshot, *};

struct LocalPlayer {
    deck: ControlDeck,
    saved: Option<(Vec<u8>, bool)>,
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
    Ok(LocalPlayer { deck, saved: None })
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
                player
                    .deck
                    .bus_mut()
                    .input
                    .joypad_mut(port)
                    .set_button(*button, mask & (1 << index) != 0);
            }
        }
        player
            .deck
            .clock_frame()
            .map(|_| ())
            .map_err(|error| error.to_string())
    }))
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
// Only pixels, PCM and error text are exposed; upstream saves may contain ROM bytes.
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
