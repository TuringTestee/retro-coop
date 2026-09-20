//! Versioned ROM-free local machine state. Audited profiles do not gate ROM loading.
use crate::{local_file, state_validation as validation};
use serde_json::{Value, json};
use sha2::{Digest, Sha256};
use tetanes_core::{bus::Bus, prelude::*};

const MAGIC: &[u8; 8] = b"RCSTATE1";
const TOKEN_LIMIT: u32 = 400_000;
const HEADER: usize = 72; // magic, compatibility identity, payload digest

pub(crate) struct Codec {
    identity: [u8; 32],
    template: Value,
    hardware: Value,
    region: NesRegion,
}
impl Codec {
    pub(crate) fn new(deck: &ControlDeck, rom: &[u8; 32], core: &[u8; 32]) -> Result<Self, String> {
        let mapper = serde_json::to_value(&deck.bus().mapper).map_err(|e| e.to_string())?;
        let settings = validate_mapper(&mapper, &mapper)?;
        let template = serde_json::to_value(deck.bus()).map_err(|e| e.to_string())?;
        let mut geometry = template["memory"].clone();
        geometry.as_object_mut().unwrap().remove("ram");
        let layout = serde_json::to_vec(&json!([geometry, settings])).unwrap();
        Ok(Self {
            identity: local_file::identity(MAGIC, deck, rom, core, &layout),
            template,
            hardware: validation::dynamic(deck),
            region: deck.region(),
        })
    }
    pub(crate) fn export(&self, deck: &ControlDeck) -> Result<Vec<u8>, String> {
        let value = json!({"hardware":validation::dynamic(deck),"mapper":deck.bus().mapper});
        self.validate(&value)?;
        let payload = serde_json::to_vec(&value).map_err(|e| e.to_string())?;
        if payload.len() > local_file::LIMIT - HEADER {
            return Err("Local state exceeds the file limit".into());
        }
        validation::preparse(&payload, TOKEN_LIMIT)?;
        let mut bytes = Vec::with_capacity(HEADER + payload.len());
        bytes.extend_from_slice(MAGIC);
        bytes.extend_from_slice(&self.identity);
        bytes.extend_from_slice(&Sha256::digest(&payload));
        bytes.extend_from_slice(&payload);
        Ok(bytes)
    }
    fn validate(&self, value: &Value) -> Result<(), String> {
        if value.as_object().is_none_or(|o| o.len() != 2) {
            return Err("Unknown local state fields".into());
        }
        validation::hardware(&self.hardware, &value["hardware"], self.region)?;
        // clock_frame synchronizes after the instruction crossing the frame end;
        // a DMA instruction can overshoot the first post-render scanline.
        validation::bound(
            &value["hardware"],
            "/ppu/scanline",
            validation::num(&self.hardware, "/ppu/vblank_scanline")? - 1,
            validation::num(&self.hardware, "/ppu/prerender_scanline")?,
        )?;
        validate_mapper(&self.template["mapper"], &value["mapper"]).map(|_| ())
    }
    pub(crate) fn info(&self) -> Value {
        json!({"identity":self.identity.iter().map(|b| format!("{b:02x}")).collect::<String>(),"limit":local_file::LIMIT})
    }
    pub(crate) fn validate_file(&self, bytes: &[u8]) -> Result<(), String> {
        self.candidate(bytes).map(|_| ())
    }
    fn candidate(&self, bytes: &[u8]) -> Result<Bus, String> {
        if !(HEADER..=local_file::LIMIT).contains(&bytes.len()) {
            return Err("Invalid local state length".into());
        }
        if &bytes[..8] != MAGIC || bytes[8..40] != self.identity {
            return Err("State belongs to a different game, core, settings or schema".into());
        }
        let payload = &bytes[HEADER..];
        if bytes[40..HEADER] != Sha256::digest(payload)[..] {
            return Err("Damaged local state".into());
        }
        // Bound parser recursion, token storage and strings before constructing JSON.
        validation::preparse(payload, TOKEN_LIMIT)?;
        let mut value: Value = serde_json::from_slice(payload).map_err(|e| e.to_string())?;
        if serde_json::to_vec(&value).unwrap() != payload {
            return Err("Noncanonical local state".into());
        }
        self.validate(&value)?;
        let mapper = value["mapper"].take();
        let mut hardware = value["hardware"].take();
        let corrupted = hardware["cpu"]
            .as_object_mut()
            .unwrap()
            .remove("corrupted")
            .unwrap()
            .as_bool()
            .unwrap();
        let ram = hardware["memory"]["ram"].take();
        hardware["memory"] = self.template["memory"].clone();
        hardware["memory"]["ram"] = ram;
        hardware["mapper"] = mapper;
        hardware["apu"]["filter_chain"] = self.template["apu"]["filter_chain"].clone();
        // Upstream integer widths/enums now decode only bounded shapes and trusted
        // allocation geometry. Derived cartridge mappings are rebuilt by load_bus.
        let mut candidate: Bus = serde_json::from_value(hardware).map_err(|e| e.to_string())?;
        candidate.cpu.corrupted = corrupted;
        Ok(candidate)
    }
    pub(crate) fn restore(&self, deck: &mut ControlDeck, bytes: &[u8]) -> Result<(), String> {
        let candidate = self.candidate(bytes)?;
        deck.load_bus(candidate).map_err(|e| e.to_string())?;
        deck.set_sample_rate(48_000.0);
        deck.clear_audio_samples();
        Ok(())
    }
}

/// This match is the single audited profile registry: it validates dynamics and
/// declares immutable fields for both identity construction and import checks.
fn validate_mapper(template: &Value, value: &Value) -> Result<Value, String> {
    validation::shape(template, value, "/mapper")?;
    let (name, original) = template.as_object().unwrap().iter().next().unwrap();
    let state = &value[name];
    let immutable: &[&str] = match name.as_str() {
        "Nrom" | "Uxrom" | "Cnrom" => &["/mirroring"],
        "Axrom" => {
            validation::bound(state, "/prg_bank", 0, 15)?;
            &[]
        }
        "Sxrom" => {
            for (path, max) in [
                ("/mmc1/write_just_occurred", 2),
                ("/mmc1/write_buffer", 31),
                ("/mmc1/shift_count", 4),
                ("/mmc1/chr0", 31),
                ("/mmc1/chr1", 31),
                ("/mmc1/prg", 15),
            ] {
                validation::bound(state, path, 0, max)?;
            }
            // Upstream dispatches on addr & 0xe000 but retains the raw mirrored
            // CHR address. Preserve it: board mapping reads this field directly.
            validation::bound(state, "/mmc1/last_chr_reg", 0xa000, 0xdfff)?;
            if ![
                json!("SingleScreenA"), json!("SingleScreenB"),
                json!("Horizontal"), json!("Vertical"),
            ].contains(&state["mmc1"]["mirroring"]) {
                return Err("MMC1 mirroring".into());
            }
            &["/submapper_num", "/prg_select", "/mmc1/revision"]
        }
        "Txrom" => &["/mapper_num", "/submapper_num", "/mmc3/revision"],
        _ => return Err(
            "Whole-state saves for this mapper profile are not yet validated; local play and battery operations remain available".into()
        ),
    };
    let mut settings = serde_json::Map::new();
    for path in immutable {
        if original.pointer(path) != state.pointer(path) {
            return Err(format!("Cartridge setting {path}"));
        }
        settings.insert((*path).into(), original.pointer(path).unwrap().clone());
    }
    // Typed u8 registers, enum values and fixed arrays bound simple bank/IRQ
    // accesses. MMC3 A12 clocks are wrapping u32 counters, never indices/lengths.
    Ok(json!({"profile":name,"settings":settings}))
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{canonical, snapshot, test_support::cartridge};
    fn codec(rom: &[u8], deck: &ControlDeck) -> Codec {
        Codec::new(deck, &Sha256::digest(rom).into(), &[3; 32]).unwrap()
    }
    fn write(deck: &mut ControlDeck, addr: u16, value: u8) {
        let bus = deck.bus_mut();
        bus.mapper.write_register(&mut bus.memory, addr, value);
        bus.mapper.clock();
        bus.mapper.clock();
    }
    fn change_mapper(deck: &mut ControlDeck, mapper: u8) {
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
    #[test]
    fn changed_banks_partial_serial_irq_and_regions_restore_then_replay() {
        for region in [NesRegion::Ntsc, NesRegion::Pal, NesRegion::Dendy] {
            for mapper in [0, 1, 2, 3, 4, 7] {
                let (rom, mut deck) = cartridge(mapper, region);
                let codec = codec(&rom, &deck);
                assert_eq!(
                    crate::checkpoint::Codec::new(&deck, &rom).is_ok(),
                    mapper == 0 && region == NesRegion::Ntsc,
                    "peer guard remains unchanged"
                );
                for _ in 0..4 {
                    let _ = deck.clock_frame().unwrap();
                }
                let old_pages = deck.bus().memory.prg_pages().to_vec();
                change_mapper(&mut deck, mapper);
                if [1, 2, 4].contains(&mapper) {
                    assert_ne!(
                        old_pages,
                        deck.bus().memory.prg_pages(),
                        "bank must actually change"
                    );
                }
                if mapper == 1 {
                    let Mapper::Sxrom(m) = &deck.bus().mapper else {
                        panic!()
                    };
                    assert_eq!(m.mmc1.shift_count, 2);
                }
                if mapper == 4 {
                    let Mapper::Txrom(m) = &deck.bus().mapper else {
                        panic!()
                    };
                    assert!(m.mmc3.irq_enabled);
                    assert_eq!(m.mmc3.irq_counter, 3);
                    assert!(m.mmc3.a12_low_clock > 0);
                }
                deck.bus_mut().memory.ram_mut()[0] = 0x71;
                let bytes = codec
                    .export(&deck)
                    .unwrap_or_else(|error| panic!("{mapper} {region:?}: {error}"));
                let before = canonical(&deck);
                let pages = deck.bus().memory.prg_pages().to_vec();
                // Export omits immutable memory arena and all allocation/layout metadata.
                let value: Value = serde_json::from_slice(&bytes[HEADER..]).unwrap();
                assert_eq!(value["hardware"]["memory"].as_object().unwrap().len(), 1);
                for _ in 0..3 {
                    let _ = deck.clock_frame().unwrap();
                }
                codec.restore(&mut deck, &bytes).unwrap();
                assert_eq!(before, canonical(&deck));
                assert_eq!(pages, deck.bus().memory.prg_pages());
                assert!(deck.audio_samples().is_empty());
                let mut expected = vec![];
                for _ in 0..3 {
                    let _ = deck.clock_frame().unwrap();
                    expected.extend_from_slice(deck.audio_samples());
                }
                let state = canonical(&deck);
                let video = deck.frame_buffer_raw().to_vec();
                codec.restore(&mut deck, &bytes).unwrap();
                let mut repeated = vec![];
                for _ in 0..3 {
                    let _ = deck.clock_frame().unwrap();
                    repeated.extend_from_slice(deck.audio_samples());
                }
                assert_eq!(state, canonical(&deck));
                assert_eq!(video, deck.frame_buffer_raw());
                // Both restores start a fresh presentation synth/filter history.
                assert_eq!(expected, repeated);
            }
        }
    }
    #[test]
    fn validation_only_uses_restore_decoder_without_replacing_progress() {
        let (rom, mut deck) = cartridge(1, NesRegion::Pal);
        let codec = codec(&rom, &deck);
        let _ = deck.clock_frame().unwrap();
        let saved = codec.export(&deck).unwrap();
        let _ = deck.clock_frame().unwrap();
        let current = snapshot(&deck);
        codec.validate_file(&saved).unwrap();
        assert_eq!(current, snapshot(&deck));
        let mut malformed = saved.clone();
        malformed[40] ^= 1;
        assert!(codec.validate_file(&malformed).is_err());
        assert_eq!(current, snapshot(&deck));
        codec.restore(&mut deck, &saved).unwrap();
        assert_ne!(current, snapshot(&deck));
        assert_eq!(codec.info()["limit"], local_file::LIMIT);
        assert_eq!(codec.info()["identity"].as_str().unwrap().len(), 64);
    }
    #[test]
    fn real_cpu_mirrored_mmc1_writes_restore_with_early_and_lazy_codecs() {
        for address in [0xa000u16, 0xa001, 0xbfff, 0xc000, 0xc001, 0xdfff] {
            let (mut rom, _) = cartridge(1, NesRegion::Ntsc);
            let mut program = vec![0x78, 0xa9, 0]; // SEI; LDA #0
            for _ in 0..5 {
                program.extend([0x8d, address as u8, (address >> 8) as u8, 0xea, 0xea]);
            }
            program.extend([0x4c, 0x1c, 0x80]); // Stay after the completed serial write.
            rom[16..16 + program.len()].copy_from_slice(&program);
            let mut deck = crate::test_support::load(&rom, NesRegion::Ntsc);
            let early = codec(&rom, &deck);
            let _ = deck.clock_frame().unwrap();
            let mapper = serde_json::to_value(&deck.bus().mapper).unwrap();
            assert_eq!(mapper["Sxrom"]["mmc1"]["last_chr_reg"], address);
            let lazy = codec(&rom, &deck);
            let bytes = early.export(&deck).unwrap();
            assert_eq!(bytes, lazy.export(&deck).unwrap());
            let saved = canonical(&deck);
            let pages = deck.bus().memory.chr_pages().to_vec();
            let mut twin = crate::test_support::load(&rom, NesRegion::Ntsc);
            early.restore(&mut twin, &bytes).unwrap();
            lazy.restore(&mut deck, &bytes).unwrap();
            assert_eq!(saved, canonical(&deck));
            assert_eq!(saved, canonical(&twin));
            assert_eq!(pages, twin.bus().memory.chr_pages());
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
    fn chr_rom_axrom_banks_and_chr_ram_are_restored_from_local_geometry() {
        use tetanes_core::memory::Src;
        for mapper in [2, 3, 7] {
            let (mut rom, _) = cartridge(mapper, NesRegion::Ntsc);
            match mapper {
                2 => {
                    rom[5] = 0;
                    rom.truncate(16 + 32768);
                }
                3 => {
                    rom[5] = 2;
                    rom.extend_from_within(16 + 32768..);
                }
                7 => {
                    let bank = rom[16..16 + 32768].to_vec();
                    rom.splice(16 + 32768..16 + 32768, bank);
                    rom[4] = 4;
                }
                _ => unreachable!(),
            }
            let mut deck = crate::test_support::load(&rom, NesRegion::Ntsc);
            let codec = codec(&rom, &deck);
            for _ in 0..2 {
                let _ = deck.clock_frame().unwrap();
            }
            let prg = deck.bus().memory.prg_pages().to_vec();
            let chr = deck.bus().memory.chr_pages().to_vec();
            write(&mut deck, 0x8000, 1);
            if mapper == 3 {
                assert_ne!(chr, deck.bus().memory.chr_pages());
            }
            if mapper == 7 {
                assert_ne!(prg, deck.bus().memory.prg_pages());
            }
            if mapper == 2 {
                deck.bus_mut().memory.region_mut(Src::Chr)[0] = 0xb7;
            }
            let saved = codec.export(&deck).unwrap();
            let before = canonical(&deck);
            write(&mut deck, 0x8000, 0);
            if mapper == 2 {
                deck.bus_mut().memory.region_mut(Src::Chr)[0] = 0;
            }
            codec.restore(&mut deck, &saved).unwrap();
            assert_eq!(before, canonical(&deck));
            if mapper == 2 {
                assert_eq!(deck.bus().memory.region_ref(Src::Chr)[0], 0xb7);
            }
        }
    }
    #[test]
    fn codec_identity_is_stable_after_play_and_pal_five_step_timing_is_valid() {
        let (rom, mut deck) = cartridge(1, NesRegion::Pal);
        let early = codec(&rom, &deck);
        for _ in 0..2 {
            let _ = deck.clock_frame().unwrap();
        }
        deck.bus_mut().apu.frame_counter.write(0x80, 0);
        let mut maximum_cycle = 0;
        for _ in 0..35 {
            let _ = deck.clock_frame().unwrap();
            maximum_cycle = maximum_cycle.max(deck.bus().apu.frame_counter.cycle);
            let bytes = early.export(&deck).unwrap();
            let late = codec(&rom, &deck);
            assert_eq!(early.identity, late.identity);
            late.restore(&mut deck, &bytes).unwrap();
        }
        assert!(
            maximum_cycle > 40_000,
            "exercise PAL's longer five-step counter"
        );
        change_mapper(&mut deck, 1);
        assert_eq!(
            early.identity,
            codec(&rom, &deck).identity,
            "changed registers are not identity settings"
        );
    }
    #[test]
    fn dma_instruction_can_cross_frame_boundary_without_losing_the_save() {
        let (mut rom, _) = cartridge(0, NesRegion::Ntsc);
        rom[16..25].copy_from_slice(&[0x78, 0xa9, 0, 0x8d, 0x14, 0x40, 0x4c, 0x03, 0x80]);
        let mut deck = crate::deck(&rom);
        let codec = codec(&rom, &deck);
        let mut overshot = false;
        for _ in 0..4 {
            let _ = deck.clock_frame().unwrap();
            overshot |= deck.bus().ppu.scanline > 240;
            let bytes = codec.export(&deck).unwrap();
            let before = canonical(&deck);
            let _ = deck.clock_frame().unwrap();
            codec.restore(&mut deck, &bytes).unwrap();
            assert_eq!(before, canonical(&deck));
        }
        assert!(
            overshot,
            "exercise a real DMA overshoot rather than a header-only case"
        );
    }
    fn payload(bytes: &[u8], payload: &[u8]) -> Vec<u8> {
        let mut out = bytes[..40].to_vec();
        out.extend_from_slice(&Sha256::digest(payload));
        out.extend_from_slice(payload);
        out
    }
    #[test]
    fn parser_caps_and_canonical_form_reject_before_typed_decode() {
        let (rom, mut deck) = cartridge(0, NesRegion::Ntsc);
        let codec = codec(&rom, &deck);
        let _ = deck.clock_frame().unwrap();
        let valid = codec.export(&deck).unwrap();
        let before = snapshot(&deck);
        let raw = &valid[HEADER..];
        let mut whitespace = raw.to_vec();
        whitespace.push(b' ');
        let mut duplicate = b"{\"hardware\":{},".to_vec();
        duplicate.extend_from_slice(&raw[1..]);
        let deep = format!("{}0{}", "[".repeat(25), "]".repeat(25)).into_bytes();
        let tokens = format!("[{}0]", "0,".repeat(TOKEN_LIMIT as usize)).into_bytes();
        let string = format!("\"{}\"", "x".repeat(257)).into_bytes();
        for (raw, expected) in [
            (whitespace, "Noncanonical"),
            (duplicate, "Noncanonical"),
            (deep, "depth cap"),
            (tokens, "token cap"),
            (string, "string cap"),
        ] {
            let error = codec
                .restore(&mut deck, &payload(&valid, &raw))
                .unwrap_err();
            assert!(error.contains(expected), "{error}");
            assert_eq!(before, snapshot(&deck));
        }
    }
    fn alter(bytes: &[u8], change: impl FnOnce(&mut Value)) -> Vec<u8> {
        let mut value: Value = serde_json::from_slice(&bytes[HEADER..]).unwrap();
        change(&mut value);
        let payload = serde_json::to_vec(&value).unwrap();
        let mut out = bytes[..40].to_vec();
        out.extend_from_slice(&Sha256::digest(&payload));
        out.extend(payload);
        out
    }
    #[test]
    fn untrusted_geometry_types_clocks_mapper_registers_and_identity_are_transactional() {
        let (rom, mut deck) = cartridge(1, NesRegion::Ntsc);
        let codec = codec(&rom, &deck);
        for _ in 0..3 {
            let _ = deck.clock_frame().unwrap();
        }
        let bytes = codec.export(&deck).unwrap();
        let mut cases = vec![
            vec![],
            vec![0; local_file::LIMIT + 1],
            bytes[..bytes.len() - 1].to_vec(),
        ];
        let mut trailing = bytes.clone();
        trailing.push(0);
        cases.push(trailing);
        for i in [0, 8, 40, HEADER] {
            let mut b = bytes.clone();
            b[i] ^= 1;
            cases.push(b);
        }
        for (path, value) in [
            (
                "/hardware/memory",
                json!({"len":u32::MAX,"ram_start":u32::MAX,"ram":[]}),
            ),
            ("/hardware/cpu/start_cycles", json!(255)),
            ("/hardware/ppu/cycle", json!(341)),
            ("/hardware/ppu/spr_count", json!(9)),
            ("/hardware/apu/frame_counter/step", json!(6)),
            ("/hardware/apu/frame_counter/cycle", json!(u32::MAX)),
            ("/hardware/input/joypads/0/index", json!(9)),
            ("/hardware/cpu/pc", json!(65536)),
            ("/hardware/cpu/addr_mode", json!("Unexpected")),
            ("/mapper/Sxrom/mmc1/shift_count", json!(5)),
            ("/mapper/Sxrom/mmc1/last_chr_reg", json!(0x9fff)),
            ("/mapper/Sxrom/mmc1/last_chr_reg", json!(0xe000)),
            ("/mapper/Sxrom/mmc1/chr0", json!(32)),
            ("/mapper/Sxrom/mmc1/revision", json!("A")),
            ("/mapper/Sxrom/submapper_num", json!(255)),
        ] {
            cases.push(alter(&bytes, |v| *v.pointer_mut(path).unwrap() = value));
        }
        cases.push(alter(&bytes, |v| {
            v["hardware"]["memory"]["ram"]
                .as_array_mut()
                .unwrap()
                .push(json!(0))
        }));
        let before = snapshot(&deck);
        deck.bus_mut().cpu.corrupted = true;
        for bad in cases {
            assert!(codec.restore(&mut deck, &bad).is_err());
            assert_eq!(before, snapshot(&deck));
            assert!(deck.bus().cpu.corrupted);
        }
        let valid = codec.export(&deck).unwrap();
        deck.bus_mut().cpu.corrupted = false;
        codec.restore(&mut deck, &valid).unwrap();
        assert!(deck.bus().cpu.corrupted);
        let different_core = Codec::new(&deck, &Sha256::digest(&rom).into(), &[4; 32]).unwrap();
        assert!(different_core.restore(&mut deck, &valid).is_err());
        let mut other_rom = rom;
        other_rom.push(1);
        let other = Codec::new(&deck, &Sha256::digest(other_rom).into(), &[3; 32]).unwrap();
        assert!(other.restore(&mut deck, &valid).is_err());
    }
    #[test]
    fn unvalidated_save_profile_never_blocks_local_play_or_battery() {
        let (rom, mut deck) = cartridge(157, NesRegion::Pal);
        assert!(
            codec_result(&rom, &deck)
                .unwrap_err()
                .contains("not yet validated")
        );
        for _ in 0..3 {
            let _ = deck.clock_frame().unwrap();
        }
        let battery =
            crate::battery::Battery::new(&deck, &Sha256::digest(rom).into(), &[3; 32]).unwrap();
        assert!(battery.export(&deck).len() > 76);
    }
    fn codec_result(rom: &[u8], deck: &ControlDeck) -> Result<(), String> {
        Codec::new(deck, &Sha256::digest(rom).into(), &[3; 32]).map(|_| ())
    }
}
