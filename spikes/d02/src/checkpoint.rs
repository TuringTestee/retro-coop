//! Experimental complete NROM/NTSC committed-frame codec for the pinned core.
//! Untrusted layout metadata never reaches the upstream Memory deserializer.
use serde_json::{Value, json};
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

fn dynamic(d: &ControlDeck) -> Value {
    let mut v = serde_json::to_value(d.bus()).unwrap();
    v["memory"] = json!({"ram": v["memory"]["ram"].take()});
    v.as_object_mut().unwrap().remove("mapper");
    v["apu"].as_object_mut().unwrap().remove("filter_chain");
    // Upstream skips this emulated hardware flag, so keep it explicitly.
    v["cpu"]["corrupted"] = d.bus().cpu.corrupted.into();
    v
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
        preparse(data)?;
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
        shape(&self.shape, v, "")?;
        for path in [
            "/region",
            "/cpu/start_cycles",
            "/cpu/end_cycles",
            "/ppu/clock_divider",
            "/ppu/vblank_scanline",
            "/ppu/prerender_scanline",
            "/ppu/emulate_warmup",
            "/ppu/skip_rendering",
            "/apu/clock_rate",
            "/apu/sample_rate",
            "/apu/sample_ratio",
            "/apu/speed",
            "/apu/skip_mixing",
            "/apu/mapper_enabled",
            "/apu/mapper_level",
            "/input/four_player",
            "/input/zapper",
        ] {
            if v.pointer(path) != self.shape.pointer(path) {
                return Err(format!("fixed setting {path}"));
            }
        }
        // Only boundaries emitted by clock_frame, not arbitrary mid-scanline dumps.
        for path in [
            "/cpu/master_clock",
            "/ppu/master_clock",
            "/apu/master_clock",
            "/apu/clock",
            "/apu/mix_clock",
        ] {
            bound(v, path, 0, 0)?;
        }
        bound(v, "/ppu/scanline", 240, 240)?;
        bound(v, "/ppu/cycle", 0, 340)?;
        for key in [
            "is_visible_scanline",
            "is_prerender_scanline",
            "is_render_scanline",
            "is_pal_spr_eval_scanline",
        ] {
            if v["ppu"][key] != false {
                return Err(format!("derived PPU flag {key}"));
            }
        }
        for (path, max) in [
            ("/ppu/spr_count", 8),
            ("/ppu/secondary_oamaddr", 32),
            ("/ppu/scroll/fine_x", 7),
            ("/ppu/scroll/v", 32767),
            ("/ppu/scroll/t", 32767),
            ("/ppu/scroll/delay_v", 32767),
            ("/ppu/scroll/delay_v_cycles", 3),
            ("/ppu/ctrl_master_slave", 1),
            ("/ppu/curr_palette", 15),
            ("/ppu/prev_palette", 15),
            ("/ppu/next_palette", 15),
            ("/ppu/oamaddr_lo", 3),
            ("/ppu/oamaddr_hi", 252),
            ("/apu/triangle/sequence", 31),
            ("/apu/dmc/output_level", 127),
            ("/apu/dmc/bytes_remaining", 4081),
            ("/apu/dmc/sample_length", 4081),
            ("/apu/dmc/bits_remaining", 8),
            ("/apu/frame_counter/step", 5),
            ("/apu/frame_counter/mode", 1),
            ("/apu/frame_counter/block_counter", 2),
            ("/apu/frame_counter/write_delay", 4),
            ("/apu/frame_counter/cycle", 40000),
            ("/apu/noise/shift", 32767),
        ] {
            bound(v, path, 0, max)?;
        }
        for path in ["/ppu/ctrl_bg_select", "/ppu/ctrl_spr_select"] {
            one_of(v, path, &[0, 4096])?;
        }
        one_of(v, "/ppu/ctrl_spr_height", &[8, 16])?;
        one_of(v, "/ppu/mask_grayscale", &[48, 63])?;
        bound(v, "/ppu/mask_emphasis", 0, 448)?;
        if num(v, "/ppu/mask_emphasis")? % 64 != 0 {
            return Err("PPU emphasis".into());
        }
        for x in v["ppu"]["palette"].as_array().unwrap() {
            if x.as_u64().is_none_or(|n| n > 63) {
                return Err("palette byte".into());
            }
        }
        for sprite in v["ppu"]["sprites"].as_array().unwrap() {
            if sprite["palette"].as_u64().is_none_or(|n| n > 31) {
                return Err("sprite palette".into());
            }
        }
        for channel in ["pulse1", "pulse2"] {
            for (field, max) in [
                ("duty", 3),
                ("duty_cycle", 7),
                ("sweep/shift", 7),
                ("sweep/period", 7),
                ("real_period", 2047),
            ] {
                bound(v, &format!("/apu/{channel}/{field}"), 0, max)?;
            }
        }
        for channel in ["pulse1", "pulse2", "noise"] {
            for field in ["volume", "counter", "divider"] {
                bound(v, &format!("/apu/{channel}/envelope/{field}"), 0, 15)?;
            }
        }
        for channel in ["pulse1", "pulse2", "triangle", "noise", "dmc"] {
            bound(v, &format!("/apu/{channel}/timer/cycle"), 0, 0)?;
            bound(v, &format!("/apu/{channel}/timer/period"), 0, 65535)?;
            bound(v, &format!("/apu/{channel}/timer/counter"), 0, 65535)?;
        }
        for group in ["joypads", "signatures"] {
            for (i, joypad) in v["input"][group].as_array().unwrap().iter().enumerate() {
                if joypad["index"].as_u64().is_none_or(|n| n > 8) {
                    return Err("joypad index".into());
                }
                if joypad["concurrent_dpad"] != self.shape["input"][group][i]["concurrent_dpad"] {
                    return Err("joypad setting".into());
                }
            }
        }
        if v["apu"]["mixed_level"]
            .as_f64()
            .is_none_or(|n| !(0.0..=1.0).contains(&n))
        {
            return Err("mixed level".into());
        }
        let fc = &v["apu"]["frame_counter"];
        let mut counter = tetanes_core::apu::frame_counter::FrameCounter::new(NesRegion::Ntsc);
        counter.mode = fc["mode"].as_u64().unwrap() as u8;
        counter.set_region(NesRegion::Ntsc);
        if fc["step_cycles"] != json!(counter.step_cycles) {
            return Err("frame-counter table".into());
        }
        if !fc["write_buffer"].is_null() && fc["write_delay"] == 0 {
            return Err("frame-counter write delay".into());
        }
        Ok(())
    }
}

fn num(v: &Value, path: &str) -> Result<u64, String> {
    v.pointer(path)
        .and_then(Value::as_u64)
        .ok_or_else(|| format!("integer {path}"))
}
fn bound(v: &Value, path: &str, min: u64, max: u64) -> Result<(), String> {
    if !(min..=max).contains(&num(v, path)?) {
        return Err(format!("range {path}"));
    }
    Ok(())
}
fn one_of(v: &Value, path: &str, values: &[u64]) -> Result<(), String> {
    if !values.contains(&num(v, path)?) {
        return Err(format!("enum {path}"));
    }
    Ok(())
}
fn shape(template: &Value, v: &Value, path: &str) -> Result<(), String> {
    if path == "/cpu/dma_oam_addr" || path == "/apu/frame_counter/write_buffer" {
        let max = if path.starts_with("/cpu") { 65535 } else { 255 };
        return if v.is_null() || v.as_u64().is_some_and(|n| n <= max) {
            Ok(())
        } else {
            Err(format!("optional integer {path}"))
        };
    }
    match (template, v) {
        (Value::Object(a), Value::Object(b)) if a.len() == b.len() => {
            for (key, t) in a {
                shape(
                    t,
                    b.get(key).ok_or_else(|| format!("field {path}/{key}"))?,
                    &format!("{path}/{key}"),
                )?;
            }
        }
        (Value::Array(a), Value::Array(b)) if a.len() == b.len() => {
            for (i, (t, x)) in a.iter().zip(b).enumerate() {
                shape(t, x, &format!("{path}/{i}"))?;
            }
        }
        (Value::Number(t), Value::Number(n)) => {
            if t.is_f64() {
                if n.as_f64()
                    .is_none_or(|n| !n.is_finite() || n.abs() > f32::MAX as f64)
                {
                    return Err(format!("float {path}"));
                }
            } else if n.as_u64().is_none_or(|n| n > u32::MAX as u64) {
                return Err(format!("integer {path}"));
            }
        }
        (Value::String(t), Value::String(s)) if s.len() <= 256 => {
            if (path.ends_with("/region") || path.ends_with("/channel")) && t != s {
                return Err(format!("fixed enum {path}"));
            }
        }
        (Value::Bool(_), Value::Bool(_)) | (Value::Null, Value::Null) => {}
        _ => return Err(format!("shape {path}")),
    }
    Ok(())
}
fn preparse(data: &[u8]) -> Result<(), String> {
    let (mut depth, mut tokens, mut in_string, mut escape, mut string_len) =
        (0u32, 0u32, false, false, 0usize);
    for &b in data {
        if in_string {
            string_len += 1;
            if string_len > 256 {
                return Err("string cap".into());
            }
            if escape {
                escape = false;
            } else if b == b'\\' {
                escape = true;
            } else if b == b'"' {
                in_string = false;
            }
        } else {
            match b {
                b'"' => {
                    in_string = true;
                    string_len = 0;
                    tokens += 1;
                }
                b'{' | b'[' => {
                    depth += 1;
                    tokens += 1;
                    if depth > 24 {
                        return Err("depth cap".into());
                    }
                }
                b'}' | b']' => {
                    depth = depth.checked_sub(1).ok_or("depth underflow")?;
                }
                b',' | b':' => tokens += 1,
                _ => {}
            }
            if tokens > 60000 {
                return Err("token cap".into());
            }
        }
    }
    if depth != 0 || in_string {
        return Err("incomplete JSON".into());
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{canonical, deck, step};

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
