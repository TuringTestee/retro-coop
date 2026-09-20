//! ROM-free battery data, not a whole-machine save or a peer checkpoint.
//! No untrusted lengths, mapper registers or memory layouts reach deserialization.
use sha2::{Digest, Sha256};
use tetanes_core::prelude::*;

const MAGIC: &[u8; 8] = b"RCBAT001";
const HEADER: usize = 8 + 32 + 4 + 32;
pub const LIMIT: usize = 2 * 1024 * 1024;

pub struct Battery {
    identity: [u8; 32],
    len: usize,
}
impl Battery {
    /// `core` is the SHA-256 of the actual loaded WASM bytes, computed by the worker.
    pub fn new(deck: &ControlDeck, rom: &[u8; 32], core: &[u8; 32]) -> Result<Self, String> {
        let len = deck.bus().memory.sram().len();
        if deck.cart_battery_backed() != Some(true) || len == 0 {
            return Err("This cartridge has no battery data".into());
        }
        if len > LIMIT - HEADER {
            return Err("Battery data exceeds the format limit".into());
        }
        let mut identity = Sha256::new();
        identity.update(MAGIC);
        identity.update(rom);
        identity.update(core);
        identity.update(serde_json::to_vec(&deck.region()).unwrap());
        identity.update(b"zero-ram;48000hz;1x;standard-p1-p2;default-mapper-revisions");
        identity.update((len as u32).to_le_bytes());
        Ok(Self {
            identity: identity.finalize().into(),
            len,
        })
    }
    pub fn export(&self, deck: &ControlDeck) -> Vec<u8> {
        // Sync EEPROM/other mapper extensions on a trusted clone; capture never changes
        // the live CPU, mapper registers, input, frame, or staged battery memory.
        let mut bus = deck.bus().clone();
        let data = bus.sram();
        let mut bytes = Vec::with_capacity(HEADER + self.len);
        bytes.extend_from_slice(MAGIC);
        bytes.extend_from_slice(&self.identity);
        bytes.extend_from_slice(&(self.len as u32).to_le_bytes());
        bytes.extend_from_slice(&Sha256::digest(data));
        bytes.extend_from_slice(data);
        bytes
    }
    pub fn restore(&self, deck: &mut ControlDeck, bytes: &[u8]) -> Result<(), String> {
        // All admission checks precede cloning/decoding/mutation. The locally loaded
        // cartridge alone supplies allocation sizes and board mappings.
        if bytes.len() != HEADER + self.len || bytes.len() > LIMIT {
            return Err("Invalid battery file length".into());
        }
        if &bytes[..8] != MAGIC || bytes[8..40] != self.identity {
            return Err(
                "Battery file belongs to a different game, core, settings or schema".into(),
            );
        }
        if bytes[40..44] != (self.len as u32).to_le_bytes() {
            return Err("Invalid battery payload length".into());
        }
        let data = &bytes[HEADER..];
        if bytes[44..HEADER] != Sha256::digest(data)[..] {
            return Err("Damaged battery data".into());
        }
        let mut candidate = deck.bus().clone();
        candidate.set_sram(data);
        deck.load_bus(candidate).map_err(|error| error.to_string())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{canonical, snapshot};
    use tetanes_core::memory::Src;
    fn fixture(mapper: u8, region: NesRegion) -> (Vec<u8>, ControlDeck) {
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
        let mut deck = ControlDeck::with_config(
            Config::default()
                .with_sram_dir(None)
                .with_ram_state(RamState::AllZeros)
                .with_region(region),
        );
        deck.load_rom("battery-diagnostic", &mut std::io::Cursor::new(&rom))
            .unwrap();
        deck.set_sample_rate(48_000.0);
        (rom, deck)
    }
    fn codec(rom: &[u8], deck: &ControlDeck) -> Battery {
        Battery::new(deck, &Sha256::digest(rom).into(), &[7; 32]).unwrap()
    }
    fn write(deck: &mut ControlDeck, addr: u16, value: u8) {
        let bus = deck.bus_mut();
        bus.mapper.write_register(&mut bus.memory, addr, value);
        bus.mapper.clock();
        bus.mapper.clock();
    }
    #[test]
    fn mmc1_bank_partial_serial_state_and_ram_survive_battery_restore() {
        let (rom, mut deck) = fixture(1, NesRegion::Ntsc);
        let initial_pages = deck.bus().memory.prg_pages().to_vec();
        for bit in [1, 0, 0, 0, 0] {
            write(&mut deck, 0xe000, bit);
        }
        assert_ne!(initial_pages, deck.bus().memory.prg_pages());
        assert!(deck.bus_mut().poke(0x6000, 0x37));
        write(&mut deck, 0xa000, 1);
        write(&mut deck, 0xa000, 0);
        let Mapper::Sxrom(mapper) = &deck.bus().mapper else {
            panic!()
        };
        assert_eq!(mapper.mmc1.shift_count, 2);
        let before_mapper = serde_json::to_value(&deck.bus().mapper).unwrap();
        let pages = deck.bus().memory.prg_pages().to_vec();
        let battery = codec(&rom, &deck);
        let before_export = snapshot(&deck);
        let saved = battery.export(&deck);
        assert_eq!(
            before_export,
            snapshot(&deck),
            "export must not mutate live state"
        );
        assert_eq!(saved.len(), HEADER + deck.sram().len());
        assert!(!saved.windows(32).any(|bytes| bytes == [0xa7; 32]));
        assert!(deck.bus_mut().poke(0x6000, 0x99));
        deck.bus_mut().cpu.corrupted = true;
        let cpu = serde_json::to_value(&deck.bus().cpu).unwrap();
        battery.restore(&mut deck, &saved).unwrap();
        assert_eq!(deck.sram()[0], 0x37);
        assert_eq!(
            serde_json::to_value(&deck.bus().mapper).unwrap(),
            before_mapper
        );
        assert_eq!(serde_json::to_value(&deck.bus().cpu).unwrap(), cpu);
        assert!(deck.bus().cpu.corrupted);
        assert_eq!(deck.bus().memory.prg_pages().as_slice(), pages);
    }
    #[test]
    fn mmc3_and_bandai_battery_extensions_roundtrip_and_replay() {
        for (mapper, region, extra) in [
            (4, NesRegion::Ntsc, 0),
            (157, NesRegion::Pal, 384),
            (159, NesRegion::Dendy, 128),
        ] {
            let (rom, mut deck) = fixture(mapper, region);
            for _ in 0..3 {
                let _ = deck.clock_frame().unwrap();
            }
            if mapper == 4 {
                write(&mut deck, 0x8000, 6);
                write(&mut deck, 0x8001, 1);
                write(&mut deck, 0xc000, 5);
                write(&mut deck, 0xe001, 0);
            }
            let battery = codec(&rom, &deck);
            assert_eq!(deck.sram().len(), 8192 + extra);
            let pattern: Vec<_> = (0..8192 + extra).map(|i| (i * 13 + 17) as u8).collect();
            deck.set_sram(&pattern);
            let saved = battery.export(&deck);
            assert_eq!(&saved[HEADER..], pattern);
            let before = canonical(&deck);
            let immutable = deck.bus().memory.region_ref(Src::PrgRom).to_vec();
            deck.set_sram(&vec![0; pattern.len()]);
            battery.restore(&mut deck, &saved).unwrap();
            assert_eq!(deck.sram(), pattern, "mapper {mapper} extension sync");
            assert_eq!(before, canonical(&deck));
            assert_eq!(deck.bus().memory.region_ref(Src::PrgRom), immutable);
            let (_, mut twin) = fixture(mapper, region);
            for _ in 0..3 {
                let _ = twin.clock_frame().unwrap();
            }
            if mapper == 4 {
                write(&mut twin, 0x8000, 6);
                write(&mut twin, 0x8001, 1);
                write(&mut twin, 0xc000, 5);
                write(&mut twin, 0xe001, 0);
            }
            twin.set_sram(&pattern);
            for _ in 0..3 {
                let _ = deck.clock_frame().unwrap();
                let _ = twin.clock_frame().unwrap();
                assert_eq!(canonical(&deck), canonical(&twin));
                assert_eq!(deck.frame_buffer_raw(), twin.frame_buffer_raw());
                assert_eq!(deck.audio_samples(), twin.audio_samples());
            }
        }
    }
    #[test]
    fn invalid_battery_files_are_transactional_and_identity_is_exact() {
        let (rom, mut deck) = fixture(1, NesRegion::Ntsc);
        let battery = codec(&rom, &deck);
        let valid = battery.export(&deck);
        let mut invalid = vec![
            vec![],
            vec![0; LIMIT + 1],
            valid[..valid.len() - 1].to_vec(),
        ];
        let mut trailing = valid.clone();
        trailing.push(0);
        invalid.push(trailing);
        for offset in [0, 8, 40, 44, HEADER] {
            let mut bytes = valid.clone();
            bytes[offset] ^= 1;
            invalid.push(bytes);
        }
        let mut huge = valid.clone();
        huge[40..44].copy_from_slice(&u32::MAX.to_le_bytes());
        invalid.push(huge);
        let mut other_rom = rom.clone();
        other_rom.push(1);
        invalid.push(codec(&other_rom, &deck).export(&deck));
        invalid.push(
            Battery::new(&deck, &Sha256::digest(&rom).into(), &[8; 32])
                .unwrap()
                .export(&deck),
        );
        let (_, pal) = fixture(1, NesRegion::Pal);
        invalid.push(codec(&rom, &pal).export(&pal));
        let before = snapshot(&deck);
        deck.bus_mut().cpu.corrupted = true;
        for bytes in invalid {
            assert!(battery.restore(&mut deck, &bytes).is_err());
            assert_eq!(before, snapshot(&deck));
            assert!(deck.bus().cpu.corrupted);
        }
        let mut no_battery = rom;
        no_battery[6] &= !2;
        let mut d = crate::deck(&no_battery);
        assert!(d.sram().is_empty());
        assert!(Battery::new(&d, &Sha256::digest(no_battery).into(), &[7; 32]).is_err());
    }
}
