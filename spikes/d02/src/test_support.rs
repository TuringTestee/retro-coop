//! Original generated cartridge fixtures shared by local file boundary tests.
use tetanes_core::prelude::*;
pub(crate) fn cartridge(mapper: u8, region: NesRegion) -> (Vec<u8>, ControlDeck) {
    let original = std::fs::read("fixture.local.nes").unwrap();
    let mut rom = original.clone();
    rom[4] = 2;
    rom.splice(
        16 + 16384..16 + 16384,
        original[16..16 + 16384].iter().copied(),
    );
    rom[6] = (mapper << 4) | 2;
    rom[7] = mapper & 0xf0;
    rom[16 + 8192..16 + 8256].fill(0xa7);
    let deck = load(&rom, region);
    (rom, deck)
}
pub(crate) fn load(rom: &[u8], region: NesRegion) -> ControlDeck {
    let mut deck = ControlDeck::with_config(
        Config::default()
            .with_sram_dir(None)
            .with_ram_state(RamState::AllZeros)
            .with_region(region),
    );
    deck.load_rom("battery-diagnostic", &mut std::io::Cursor::new(&rom))
        .unwrap();
    deck.set_sample_rate(48_000.0);
    deck
}
