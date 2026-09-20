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

pub(crate) fn write(deck: &mut ControlDeck, addr: u16, value: u8) {
    let bus = deck.bus_mut();
    bus.mapper.write_register(&mut bus.memory, addr, value);
    bus.mapper.clock();
    bus.mapper.clock();
}
pub(crate) fn change_mapper(deck: &mut ControlDeck, mapper: u8) {
    match mapper {
        1 => {
            for bit in [1, 0, 0, 0, 0] {
                write(deck, 0xe000, bit)
            }
            write(deck, 0xa000, 1);
            write(deck, 0xa000, 0);
        }
        2 | 3 | 7 => write(deck, 0x8000, 1),
        4 => {
            write(deck, 0x8000, 6);
            write(deck, 0x8001, 2);
            write(deck, 0xa000, 1);
            write(deck, 0xc000, 3);
            write(deck, 0xc001, 0);
            write(deck, 0xe001, 0);
            let bus = deck.bus_mut();
            bus.mapper.ppu_bus_addr(&mut bus.memory, 0);
            for _ in 0..6 {
                bus.mapper.clock();
            }
            bus.mapper.ppu_bus_addr(&mut bus.memory, 0x1000);
            bus.mapper.ppu_bus_addr(&mut bus.memory, 0);
        }
        _ => {}
    }
}
