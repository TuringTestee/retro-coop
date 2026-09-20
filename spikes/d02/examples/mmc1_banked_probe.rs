//! Read an original CPU diagnostic and assert its observed RAM/bank results.
use tetanes_core::prelude::*;
fn main() {
    let args: Vec<_> = std::env::args().collect();
    assert_eq!(args.len(), 3, "mmc1_banked_probe CASE ROM");
    let rom = std::fs::read(&args[2]).unwrap();
    let mut deck = ControlDeck::with_config(
        Config::default()
            .with_sram_dir(None)
            .with_ram_state(RamState::AllZeros)
            .with_region(NesRegion::Ntsc),
    );
    deck.load_rom("original-mmc1-probe", &mut std::io::Cursor::new(&rom))
        .unwrap();
    for _ in 0..3 {
        deck.clock_frame().unwrap();
        if deck.bus().wram[0x20] == 0x80 {
            break;
        }
    }
    assert_eq!(deck.bus().wram[0x20], 0x80, "CPU did not complete diagnostic");
    let expected: &[u8] = match args[1].as_str() {
        "banked" => &[0x11, 0x22, 0x33, 0x44],
        "mirrored" | "mirrored-control" => &[16],
        _ => panic!("unknown case"),
    };
    let observed = &deck.bus().wram()[0x10..0x10 + expected.len()];
    println!("case={} observed={observed:?} expected={expected:?}", args[1]);
    assert_eq!(observed, expected, "CPU-visible mapper behavior differs");
}
