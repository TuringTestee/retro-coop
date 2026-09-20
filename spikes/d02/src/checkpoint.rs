//! Experimental complete NROM/NTSC committed-frame codec for the pinned core.
//! Untrusted layout metadata never reaches the upstream Memory deserializer.
use crate::state_validation::{dynamic, preparse};
use serde_json::Value;
use sha2::{Digest, Sha256};
use tetanes_core::{bus::Bus, prelude::*};

pub const LIMIT: usize = 2 * 1024 * 1024;
const MAGIC: &[u8; 8] = b"D02NES01";
const HEADER: usize = 40;
const CORE: &str = "a0a6b17f8ba9c5ee451453fb2409753fd06e5a31";

pub struct Codec {
    identity: [u8; 32],
    template: Value,
    shape: Value,
}

impl Codec {
    pub fn new(d: &ControlDeck, rom: &[u8]) -> Result<Self, String> {
        if !matches!(d.bus().mapper, Mapper::Nrom(_)) || d.region() != NesRegion::Ntsc {
            return Err("prototype codec admits only NROM/NTSC".into());
        }
        let template = serde_json::to_value(d.bus()).map_err(|e| e.to_string())?;
        let shape = dynamic(d);
        let mut fingerprint = Sha256::new();
        fingerprint.update(MAGIC);
        fingerprint.update(CORE);
        fingerprint.update(include_bytes!("../Cargo.lock"));
        fingerprint.update(include_bytes!("../rust-toolchain.toml"));
        fingerprint.update(include_bytes!("../.cargo/config.toml"));
        fingerprint.update(Sha256::digest(rom));
        fingerprint.update(b"NTSC;zero-RAM;48kHz;1x;two-standard-controllers;frame-boundary");
        let mut layout = template["memory"].clone();
        layout.as_object_mut().unwrap().remove("ram");
        fingerprint.update(serde_json::to_vec(&layout).unwrap());
        fingerprint.update(serde_json::to_vec(&template["mapper"]).unwrap());
        Ok(Self {
            identity: fingerprint.finalize().into(),
            template,
            shape,
        })
    }

    pub fn encode(&self, d: &ControlDeck) -> Result<Vec<u8>, String> {
        let state = dynamic(d);
        self.validate(&state)?;
        let json = serde_json::to_vec(&state).map_err(|e| e.to_string())?;
        if HEADER + json.len() > LIMIT {
            return Err("checkpoint over limit".into());
        }
        let mut bytes = Vec::with_capacity(HEADER + json.len());
        bytes.extend_from_slice(MAGIC);
        bytes.extend_from_slice(&self.identity);
        bytes.extend_from_slice(&json);
        Ok(bytes)
    }

    pub fn decode(&self, bytes: &[u8]) -> Result<Bus, String> {
        if !(HEADER..=LIMIT).contains(&bytes.len()) {
            return Err("checkpoint length".into());
        }
        if &bytes[..8] != MAGIC || bytes[8..HEADER] != self.identity {
            return Err("checkpoint identity/schema".into());
        }
        let data = &bytes[HEADER..];
        preparse(data, 60000)?;
        let mut v: Value = serde_json::from_slice(data).map_err(|e| e.to_string())?;
        // Exact canonical encoding rejects duplicate keys, trailing material and alternate
        // representations; max-depth/token/string checks have already bounded parsing.
        if serde_json::to_vec(&v).unwrap() != data {
            return Err("noncanonical JSON".into());
        }
        self.validate(&v)?;
        let corrupted = v["cpu"]
            .as_object_mut()
            .unwrap()
            .remove("corrupted")
            .unwrap()
            .as_bool()
            .unwrap();
        let ram = v["memory"]["ram"].take();
        v["memory"] = self.template["memory"].clone();
        v["memory"]["ram"] = ram;
        v["mapper"] = self.template["mapper"].clone();
        v["apu"]["filter_chain"] = self.template["apu"]["filter_chain"].clone();
        // Shape lengths and allocation-driving fields are now trusted. Upstream typed
        // decoding enforces its integer widths, enum discriminants and fixed arrays.
        let mut bus: Bus = serde_json::from_value(v).map_err(|e| e.to_string())?;
        bus.cpu.corrupted = corrupted;
        Ok(bus)
    }

    pub fn restore(&self, d: &mut ControlDeck, bytes: &[u8]) -> Result<(), String> {
        let bus = self.decode(bytes)?;
        d.load_bus(bus).map_err(|e| e.to_string())?;
        // A timeline jump starts a new presentation-audio epoch on every participant.
        // Hardware APU channel/counter state is preserved; pending old audio is discarded.
        d.set_sample_rate(48_000.0);
        d.clear_audio_samples();
        Ok(())
    }

    fn validate(&self, v: &Value) -> Result<(), String> {
        crate::state_validation::hardware(&self.shape, v, NesRegion::Ntsc)?;
        crate::state_validation::bound(
            v,
            "/ppu/scanline",
            u64::from(tetanes_core::ppu::scanline::POSTRENDER),
            u64::from(tetanes_core::ppu::scanline::POSTRENDER),
        )
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{canonical, deck, step};
    use serde_json::json;

    fn fixture() -> (Vec<u8>, ControlDeck, Codec) {
        let rom = std::fs::read("fixture.local.nes")
            .expect("run original_fixture.py fixture.local.nes first");
        let mut d = deck(&rom);
        let codec = Codec::new(&d, &rom).unwrap();
        for f in 0..60 {
            step(&mut d, f);
        }
        (rom, d, codec)
    }
    fn mutated(bytes: &[u8], change: impl FnOnce(&mut Value)) -> Vec<u8> {
        let mut v: Value = serde_json::from_slice(&bytes[HEADER..]).unwrap();
        change(&mut v);
        let mut result = bytes[..HEADER].to_vec();
        result.extend(serde_json::to_vec(&v).unwrap());
        result
    }

    #[test]
    fn complete_roundtrip_restores_hardware_and_new_audio_epoch() {
        let (_, mut d, codec) = fixture();
        assert!(d.bus().wram[2] > 0, "original diagnostic executes");
        assert!(
            d.audio_samples().iter().any(|x| *x != 0.0),
            "original diagnostic produces audio"
        );
        let bytes = codec.encode(&d).unwrap();
        let initial = canonical(&d);
        for f in 60..91 {
            step(&mut d, f);
        }
        codec.restore(&mut d, &bytes).unwrap();
        assert!(d.audio_samples().is_empty());
        assert_eq!(initial, canonical(&d));
        let mut first_audio = vec![];
        for f in 60..120 {
            step(&mut d, f);
            first_audio.extend_from_slice(d.audio_samples());
        }
        let first = canonical(&d);
        for f in 120..177 {
            step(&mut d, f);
        }
        codec.restore(&mut d, &bytes).unwrap();
        let mut second_audio = vec![];
        for f in 60..120 {
            step(&mut d, f);
            second_audio.extend_from_slice(d.audio_samples());
        }
        assert_eq!(first, canonical(&d));
        assert_eq!(first_audio, second_audio);
        assert!((47000..49000).contains(&first_audio.len()));
        assert!(bytes.len() < LIMIT);
    }

    #[test]
    fn preserves_cpu_jam_flag_which_upstream_omits() {
        let (_, mut d, codec) = fixture();
        d.bus_mut().cpu.corrupted = true;
        let bytes = codec.encode(&d).unwrap();
        d.bus_mut().cpu.corrupted = false;
        codec.restore(&mut d, &bytes).unwrap();
        assert!(d.bus().cpu.corrupted);
    }

    #[test]
    fn adversarial_inputs_fail_before_mutating_live_core() {
        let (_, mut d, codec) = fixture();
        let bytes = codec.encode(&d).unwrap();
        let before = canonical(&d);
        let mut cases = vec![
            vec![],
            vec![0; LIMIT + 1],
            bytes[..bytes.len() - 1].to_vec(),
        ];
        let mut unknown = bytes.clone();
        unknown[0] ^= 1;
        cases.push(unknown);
        let mut mismatch = bytes.clone();
        mismatch[8] ^= 1;
        cases.push(mismatch);
        let mut trailing = bytes.clone();
        trailing.push(0);
        cases.push(trailing);
        for (path, value) in [
            ("/memory/ram", json!([])),
            ("/cpu/cycle", json!(-1)),
            ("/cpu/addr_mode", json!("unknown")),
            ("/cpu/start_cycles", json!(0)),
            ("/ppu/clock_divider", json!(0)),
            ("/ppu/scanline", json!(999)),
            ("/ppu/scroll/fine_x", json!(16)),
            ("/ppu/secondary_oamaddr", json!(255)),
            ("/ppu/spr_count", json!(255)),
            ("/ppu/is_visible_scanline", json!(true)),
            ("/apu/master_clock", json!(4294967295u32)),
            ("/apu/pulse1/duty", json!(255)),
            ("/apu/pulse1/duty_cycle", json!(8)),
            ("/apu/pulse1/sweep/shift", json!(255)),
            ("/apu/noise/envelope/volume", json!(255)),
            ("/apu/triangle/sequence", json!(32)),
            ("/apu/dmc/output_level", json!(128)),
            ("/apu/frame_counter/step", json!(6)),
            ("/apu/frame_counter/step_cycles", json!([0, 0, 0, 0, 0, 0])),
            ("/input/joypads/0/index", json!(255)),
            ("/apu/sample_rate", json!(0.0)),
        ] {
            cases.push(mutated(&bytes, |v| *v.pointer_mut(path).unwrap() = value));
        }
        cases.push(mutated(&bytes, |v| {
            v["memory"]["len"] = json!(4294967295u32)
        }));
        cases.push(mutated(&bytes, |v| v["unknown"] = json!(true)));
        cases.push(mutated(&bytes, |v| {
            v["apu"]["frame_counter"]["write_buffer"] = json!(1);
            v["apu"]["frame_counter"]["write_delay"] = json!(0);
        }));
        let mut deep = bytes[..HEADER].to_vec();
        deep.extend(vec![b'['; 25]);
        deep.extend(vec![b']'; 25]);
        cases.push(deep);
        let mut huge = bytes[..HEADER].to_vec();
        huge.extend_from_slice(b"{\"a\":1e999}");
        cases.push(huge);
        for (i, invalid) in cases.into_iter().enumerate() {
            assert!(
                codec.restore(&mut d, &invalid).is_err(),
                "case {i} accepted"
            );
            assert_eq!(before, canonical(&d), "case {i} mutated live state");
        }
    }
}
