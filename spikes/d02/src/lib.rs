//! Trusted-local feasibility probe. Never expose raw upstream snapshots to peers.
use std::cell::RefCell;
mod battery;
pub mod checkpoint;
mod local_file;
pub mod local_player;
mod local_state;
pub mod memory_tail;
mod state_validation;
#[cfg(test)]
mod test_support;
use tetanes_core::{
    input::{JoypadBtnState, Player},
    prelude::*,
};

struct Probe {
    deck: ControlDeck,
    codec: checkpoint::Codec,
    saved: Vec<u8>,
    output: Vec<u8>,
}
thread_local! { static PROBE: RefCell<Option<Probe>> = const { RefCell::new(None) }; }

pub fn deck(rom: &[u8]) -> ControlDeck {
    let mut d = ControlDeck::with_config(
        Config::default()
            .with_sram_dir(None)
            .with_ram_state(RamState::AllZeros)
            .with_filter(tetanes_core::video::VideoFilter::Pixellate)
            .with_region(NesRegion::Ntsc),
    );
    d.load_rom("authorized-fixture", &mut std::io::Cursor::new(rom))
        .unwrap();
    d.set_sample_rate(48_000.0);
    d
}

pub fn snapshot(d: &ControlDeck) -> Vec<u8> {
    let mut bytes = vec![0; d.serialized_state_len().unwrap()];
    d.serialize_state_into(&mut bytes).unwrap();
    bytes
}

pub fn step(d: &mut ControlDeck, frame: u32) {
    for (player, phase) in [(Player::One, 0), (Player::Two, 37)] {
        for (i, button) in [
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
            d.bus_mut()
                .input
                .joypad_mut(player)
                .set_button(*button, ((frame + phase) / (11 + i as u32 * 7)) % 2 == 1);
        }
    }
    let _ = d.clock_frame().unwrap();
}

// Tiny WASM ABI avoids a frontend framework. Input ROM lives only in browser memory.
// Raw snapshots are created/restored internally, never accepted from JavaScript/peers.
#[unsafe(no_mangle)]
pub extern "C" fn input_alloc(len: usize) -> *mut u8 {
    assert!(len <= 8 * 1024 * 1024);
    let mut b = vec![0; len].into_boxed_slice();
    let p = b.as_mut_ptr();
    std::mem::forget(b);
    p
}
#[unsafe(no_mangle)]
pub unsafe extern "C" fn initialize(ptr: *mut u8, len: usize) {
    let rom = unsafe { Box::from_raw(std::ptr::slice_from_raw_parts_mut(ptr, len)) };
    let deck = deck(&rom);
    let codec = checkpoint::Codec::new(&deck, &rom).unwrap();
    PROBE.with_borrow_mut(|p| {
        *p = Some(Probe {
            deck,
            codec,
            saved: vec![],
            output: vec![],
        })
    });
}
#[unsafe(no_mangle)]
pub extern "C" fn advance(frame: u32, count: u32) {
    PROBE.with_borrow_mut(|p| {
        let p = p.as_mut().unwrap();
        for f in frame..frame + count {
            step(&mut p.deck, f);
        }
    });
}
/// Explicit two-controller input for the trusted-local realtime experiment.
#[unsafe(no_mangle)]
pub extern "C" fn advance_inputs(one: u8, two: u8) {
    PROBE.with_borrow_mut(|p| {
        let p = p.as_mut().unwrap();
        for (player, mask) in [(Player::One, one), (Player::Two, two)] {
            for (i, button) in [
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
                p.deck
                    .bus_mut()
                    .input
                    .joypad_mut(player)
                    .set_button(*button, mask & (1 << i) != 0);
            }
        }
        let _ = p.deck.clock_frame().unwrap();
    });
}
#[unsafe(no_mangle)]
pub extern "C" fn manual_frame(one: u8, two: u8) {
    advance_inputs(one, two);
}
#[unsafe(no_mangle)]
pub extern "C" fn save() -> usize {
    PROBE.with_borrow_mut(|p| {
        let p = p.as_mut().unwrap();
        p.saved = p.codec.encode(&p.deck).unwrap();
        p.saved.len()
    })
}
#[unsafe(no_mangle)]
pub extern "C" fn restore() {
    PROBE.with_borrow_mut(|p| {
        let p = p.as_mut().unwrap();
        p.codec.restore(&mut p.deck, &p.saved).unwrap();
    });
}
#[unsafe(no_mangle)]
pub extern "C" fn output(kind: u32) -> *const u8 {
    PROBE.with_borrow_mut(|p| {
        let p = p.as_mut().unwrap();
        p.output = match kind {
            0 => snapshot(&p.deck),
            1 => p
                .deck
                .frame_buffer_raw()
                .iter()
                .flat_map(|x| x.to_le_bytes())
                .collect(),
            2 => p
                .deck
                .audio_samples()
                .iter()
                .flat_map(|x| x.to_le_bytes())
                .collect(),
            3 => serde_json::to_vec(p.deck.bus()).unwrap(),
            5 => p.deck.frame_buffer().to_vec(),
            _ => canonical(&p.deck),
        };
        p.output.as_ptr()
    })
}
#[unsafe(no_mangle)]
pub extern "C" fn output_len() -> usize {
    PROBE.with_borrow(|p| p.as_ref().unwrap().output.len())
}

/// Research canonical state: only the output filter history is excluded.
/// This is not a peer encoding or a validated import schema.
pub fn canonical(d: &ControlDeck) -> Vec<u8> {
    let mut state = serde_json::to_value(d.bus()).unwrap();
    state["cpu"]["corrupted"] = d.bus().cpu.corrupted.into();
    state["apu"].as_object_mut().unwrap().remove("filter_chain");
    serde_json::to_vec(&state).unwrap()
}

#[unsafe(no_mangle)]
pub extern "C" fn rewind_probe(start: u32) -> *const u8 {
    PROBE.with_borrow_mut(|p| {
        let p = p.as_mut().unwrap();
        let mut ring = Vec::with_capacity(601);
        ring.push(snapshot(&p.deck));
        for f in start..start + 600 {
            step(&mut p.deck, f);
            ring.push(snapshot(&p.deck));
        }
        let tracked_bytes = ring.capacity() * std::mem::size_of::<Vec<u8>>()
            + ring.iter().map(|v| v.capacity()).sum::<usize>();
        assert!(tracked_bytes <= 32 * 1024 * 1024);
        let expected = canonical(&p.deck);
        let (bus, consumed) =
            bincode::serde::decode_from_slice(&ring[0], bincode::config::legacy()).unwrap();
        assert_eq!(consumed, ring[0].len());
        p.deck.load_bus(bus).unwrap();
        for f in start..start + 600 {
            step(&mut p.deck, f);
        }
        p.output = serde_json::to_vec(&serde_json::json!({
            "retained_snapshots":ring.len(), "tracked_allocation_bytes":tracked_bytes,
            "frames_rewound":600, "canonical_replay_equal":expected == canonical(&p.deck),
            "max_snapshot_bytes":ring.iter().map(Vec::len).max().unwrap(),
        }))
        .unwrap();
        p.output.as_ptr()
    })
}

#[cfg(test)]
mod realtime_tests {
    use super::*;

    #[test]
    fn presentation_filter_preserves_core_checkpoint_and_raw_video() {
        let rom = std::fs::read("fixture.local.nes").unwrap();
        let mut pixels = deck(&rom);
        let mut ntsc = deck(&rom);
        ntsc.set_filter(tetanes_core::video::VideoFilter::Ntsc);
        let pixel_codec = checkpoint::Codec::new(&pixels, &rom).unwrap();
        let ntsc_codec = checkpoint::Codec::new(&ntsc, &rom).unwrap();
        let mut presentation_differs = false;
        for frame in 0..120 {
            step(&mut pixels, frame);
            step(&mut ntsc, frame);
            assert_eq!(pixels.frame_buffer_raw(), ntsc.frame_buffer_raw());
            presentation_differs |= pixels.frame_buffer() != ntsc.frame_buffer();
            assert_eq!(canonical(&pixels), canonical(&ntsc));
            assert_eq!(
                pixel_codec.encode(&pixels).unwrap(),
                ntsc_codec.encode(&ntsc).unwrap()
            );
        }
        assert!(presentation_differs);
    }

    #[test]
    fn manual_controller_ports_render_and_release() {
        let rom = std::fs::read("fixture.local.nes").unwrap();
        let deck = deck(&rom);
        let codec = checkpoint::Codec::new(&deck, &rom).unwrap();
        PROBE.with_borrow_mut(|p| {
            *p = Some(Probe {
                deck,
                codec,
                saved: vec![],
                output: vec![],
            });
        });
        for _ in 0..4 {
            manual_frame(1, 2);
        }
        PROBE.with_borrow(|p| {
            let p = p.as_ref().unwrap();
            assert_eq!(&p.deck.bus().wram[0..2], &[128, 64]);
            assert!(p.deck.audio_samples().iter().any(|x| x.abs() > 0.001));
        });
        output(5);
        assert_eq!(output_len(), 256 * 240 * 4);
        PROBE.with_borrow(|p| {
            assert!(
                p.as_ref()
                    .unwrap()
                    .output
                    .chunks_exact(4)
                    .all(|rgba| rgba[3] == 255)
            );
        });
        for _ in 0..3 {
            manual_frame(0, 0);
        }
        PROBE.with_borrow(|p| assert_eq!(&p.as_ref().unwrap().deck.bus().wram[0..2], &[0, 0]));
        output(5);
        let released_pixels = PROBE.with_borrow(|p| p.as_ref().unwrap().output.clone());
        for _ in 0..3 {
            manual_frame(128, 0);
        }
        output(5);
        PROBE.with_borrow(|p| assert_ne!(p.as_ref().unwrap().output, released_pixels));
    }
}
