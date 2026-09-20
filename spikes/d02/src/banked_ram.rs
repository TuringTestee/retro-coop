//! Qualification of original CPU-written banked RAM through existing file/history owners.
use crate::{battery::Battery, local_player::clock_inputs, local_state::Codec, rewind::History};
use sha2::{Digest, Sha256};
use tetanes_core::{memory::Src, prelude::*};

fn fixture(case: &str, region: NesRegion) -> (Vec<u8>, ControlDeck) {
    let rom = std::fs::read(format!("{case}.local.nes")).unwrap();
    let mut deck = crate::test_support::load(&rom, region);
    clock_inputs(&mut deck, 0, 0).unwrap();
    assert_eq!(deck.bus().wram()[0x20], 0x80, "CPU completion: {case}");
    (rom, deck)
}

#[test]
fn cpu_banks_mirrors_enable_and_serial_reset_follow_board_wiring() {
    for (case, expected) in [
        ("banked", &[0x11, 0x22, 0x33, 0x44][..]),
        ("sorom", &[0x11, 0x22][..]),
        ("single-bank", &[0x44, 0x44, 0x44, 0x44][..]),
        ("large-chr", &[0x44, 0x44, 0x44, 0x44][..]),
        ("mmc1a", &[0x11, 0x22, 0x33, 0x44][..]),
        (
            "banked-controls",
            &[0x11, 0x22, 0x33, 0x44, 0x44, 0x44, 0x11][..],
        ),
        ("banked-partial", &[0x11, 0x22, 0x33, 0x44][..]),
        ("mirrored", &[16][..]),
        ("mirrored-control", &[16][..]),
    ] {
        let (_, deck) = fixture(case, NesRegion::Ntsc);
        assert_eq!(
            &deck.bus().wram()[0x10..0x10 + expected.len()],
            expected,
            "{case}"
        );
        let ram_len = if case == "sorom" {
            16384
        } else if case == "single-bank" {
            8192
        } else {
            32768
        };
        assert_eq!(deck.bus().memory.region_ref(Src::PrgRam).len(), ram_len);
        eprintln!("CPU mapping {case}: {expected:?}, RAM bytes={ram_len}");
    }
}

#[test]
fn banked_state_battery_partial_serial_and_invalid_imports_share_existing_owners() {
    for region in [NesRegion::Ntsc, NesRegion::Pal, NesRegion::Dendy] {
        for case in ["sorom", "banked-partial"] {
            let (rom, mut deck) = fixture(case, region);
            let hash = Sha256::digest(&rom).into();
            let codec = Codec::new(&deck, &hash, &[7; 32]).unwrap();
            let battery = Battery::new(&deck, &hash, &[7; 32]).unwrap();
            let saved = codec.export(&deck).unwrap();
            let battery_saved = battery.export(&deck);
            let banks = deck.bus().memory.region_ref(Src::PrgRam).to_vec();
            let immutable = deck.bus().memory.region_ref(Src::PrgRom).to_vec();
            assert_eq!(banks.len(), if case == "sorom" { 16384 } else { 32768 });
            assert_eq!(banks[0], 0x11);
            assert_eq!(banks[8192], 0x22);
            if case == "banked-partial" {
                assert_eq!(banks[16384], 0x33);
                assert_eq!(banks[24576], 0x44);
                let Mapper::Sxrom(mapper) = &deck.bus().mapper else {
                    panic!()
                };
                assert_eq!(mapper.mmc1.shift_count, 2);
            }
            for i in 0..5 {
                clock_inputs(&mut deck, i, i + 1).unwrap();
            }
            let advanced = codec.export(&deck).unwrap();
            for (bytes, whole_state) in [(&saved, true), (&battery_saved, false)] {
                let mut damaged = bytes.clone();
                *damaged.last_mut().unwrap() ^= 1;
                let result = if whole_state {
                    codec.restore(&mut deck, &damaged)
                } else {
                    battery.restore(&mut deck, &damaged)
                };
                assert!(result.is_err());
                assert_eq!(
                    codec.export(&deck).unwrap(),
                    advanced,
                    "invalid import changes timeline"
                );
            }
            let before_mapper = serde_json::to_value(&deck.bus().mapper).unwrap();
            let before_cpu = serde_json::to_value(&deck.bus().cpu).unwrap();
            deck.bus_mut().memory.region_mut(Src::PrgRam).fill(0);
            battery.restore(&mut deck, &battery_saved).unwrap();
            assert_eq!(deck.bus().memory.region_ref(Src::PrgRam), banks);
            assert_eq!(
                serde_json::to_value(&deck.bus().mapper).unwrap(),
                before_mapper
            );
            assert_eq!(serde_json::to_value(&deck.bus().cpu).unwrap(), before_cpu);
            codec.restore(&mut deck, &saved).unwrap();
            assert_eq!(codec.export(&deck).unwrap(), saved);
            assert_eq!(deck.bus().memory.region_ref(Src::PrgRom), immutable);
            for i in 0..5 {
                clock_inputs(&mut deck, i, i + 1).unwrap();
            }
            assert_eq!(
                codec.export(&deck).unwrap(),
                advanced,
                "exact banked replay"
            );
            let incompatible = Codec::new(&deck, &hash, &[8; 32]).unwrap();
            assert!(incompatible.restore(&mut deck, &saved).is_err());
            assert_eq!(codec.export(&deck).unwrap(), advanced);
            eprintln!(
                "banked save/battery {case} {region:?}: {} RAM bytes, partial state and exact replay",
                banks.len()
            );
        }
    }
}

#[test]
fn cpu_written_banked_progress_rewinds_ten_actual_regional_seconds() {
    for region in [NesRegion::Ntsc, NesRegion::Pal, NesRegion::Dendy] {
        let (rom, mut deck) = fixture("banked-progress", region);
        let codec = Codec::new(&deck, &Sha256::digest(&rom).into(), &[7; 32]).unwrap();
        let first = codec.export(&deck).unwrap();
        let mut history = History::new(&deck);
        history.record(&mut deck, &codec, 0, 0).unwrap();
        let mut trace = vec![0u64];
        let mut cycles = 0;
        let mut previous = deck.bus().cpu.cycle;
        let rate = f64::from(deck.clock_rate());
        while (cycles as f64) < rate * 11.25 {
            clock_inputs(&mut deck, 0, 0).unwrap();
            cycles += u64::from(deck.bus().cpu.cycle.wrapping_sub(previous));
            previous = deck.bus().cpu.cycle;
            trace.push(cycles);
            history.record(&mut deck, &codec, 0, 0).unwrap();
        }
        let original = codec.export(&deck).unwrap();
        let desired = cycles as f64 - rate * 10.0;
        let target = trace.iter().rposition(|&n| n as f64 <= desired).unwrap();
        let pixels = history.rewind(&mut deck, &codec, 10.0).unwrap();
        let (_, mut reference) = fixture("banked-progress", region);
        codec.restore(&mut reference, &first).unwrap();
        for _ in 0..target {
            clock_inputs(&mut reference, 0, 0).unwrap();
        }
        assert_eq!(
            codec.export(&deck).unwrap(),
            codec.export(&reference).unwrap()
        );
        assert_eq!(pixels, reference.frame_buffer());
        assert!((cycles - trace[target]) as f64 / rate >= 10.0);
        let info = history.info();
        assert!(info["retainedBytes"].as_u64().unwrap() <= 32 * 1024 * 1024);
        assert!(info["peakBytes"].as_u64().unwrap() <= 32 * 1024 * 1024);
        for _ in target + 1..trace.len() {
            clock_inputs(&mut deck, 0, 0).unwrap();
        }
        assert_eq!(codec.export(&deck).unwrap(), original);
        eprintln!("banked regional rewind {region:?}: target={target} cycles={cycles} info={info}");
    }
}
