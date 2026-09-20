//! Shared bounded hardware validation for the peer experiment and local save profiles.
use serde_json::{Value, json};
use tetanes_core::prelude::*;

pub(crate) fn dynamic(d: &ControlDeck) -> Value {
    let mut v = serde_json::to_value(d.bus()).unwrap();
    v["memory"] = json!({"ram": v["memory"]["ram"].take()});
    v.as_object_mut().unwrap().remove("mapper");
    v["apu"].as_object_mut().unwrap().remove("filter_chain");
    // Upstream skips this emulated hardware flag, so keep it explicitly.
    v["cpu"]["corrupted"] = d.bus().cpu.corrupted.into();
    v
}

pub(crate) fn hardware(template: &Value, v: &Value, region: NesRegion) -> Result<(), String> {
    shape(template, v, "")?;
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
        if v.pointer(path) != template.pointer(path) {
            return Err(format!("fixed setting {path}"));
        }
    }
    // Only boundaries emitted by clock_frame, not arbitrary mid-scanline dumps.
    // clock_sync leaves the CPU's sub-dot remainder. PAL's 16:5 ratio
    // permits residues 0..4; other regions retain their trusted power-on phase.
    let divider = num(template, "/ppu/clock_divider")?;
    let (mut gcd, mut clocks) = (
        divider,
        num(template, "/cpu/start_cycles")? + num(template, "/cpu/end_cycles")?,
    );
    while clocks != 0 {
        (gcd, clocks) = (clocks, gcd % clocks);
    }
    bound(v, "/cpu/master_clock", 0, divider - 1)?;
    if num(v, "/cpu/master_clock")? % gcd != num(template, "/cpu/master_clock")? % gcd {
        return Err("CPU/PPU clock alignment".into());
    }
    for path in [
        "/ppu/master_clock",
        "/apu/master_clock",
        "/apu/clock",
        "/apu/mix_clock",
    ] {
        bound(v, path, 0, 0)?;
    }
    let scanline = num(v, "/ppu/scanline")?;
    let prerender = num(template, "/ppu/prerender_scanline")?;
    let vblank = num(template, "/ppu/vblank_scanline")?;
    bound(v, "/ppu/scanline", 0, prerender)?;
    bound(v, "/ppu/cycle", 0, u64::from(tetanes_core::ppu::cycle::END))?;
    for (key, expected) in [
        (
            "is_visible_scanline",
            scanline <= u64::from(tetanes_core::ppu::scanline::VISIBLE_END),
        ),
        ("is_prerender_scanline", scanline == prerender),
        (
            "is_render_scanline",
            scanline <= u64::from(tetanes_core::ppu::scanline::VISIBLE_END)
                || scanline == prerender,
        ),
        (
            "is_pal_spr_eval_scanline",
            region == NesRegion::Pal && scanline >= vblank + 24,
        ),
    ] {
        if v["ppu"][key] != expected {
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
            if joypad["concurrent_dpad"] != template["input"][group][i]["concurrent_dpad"] {
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
    let mut counter = tetanes_core::apu::frame_counter::FrameCounter::new(region);
    counter.mode = fc["mode"].as_u64().unwrap() as u8;
    counter.set_region(region);
    bound(
        v,
        "/apu/frame_counter/cycle",
        0,
        counter.step_cycles[fc["step"].as_u64().unwrap() as usize] as u64,
    )?;
    if fc["step_cycles"] != json!(counter.step_cycles) {
        return Err("frame-counter table".into());
    }
    if !fc["write_buffer"].is_null() && fc["write_delay"] == 0 {
        return Err("frame-counter write delay".into());
    }
    Ok(())
}

pub(crate) fn num(v: &Value, path: &str) -> Result<u64, String> {
    v.pointer(path)
        .and_then(Value::as_u64)
        .ok_or_else(|| format!("integer {path}"))
}
pub(crate) fn bound(v: &Value, path: &str, min: u64, max: u64) -> Result<(), String> {
    if !(min..=max).contains(&num(v, path)?) {
        return Err(format!("range {path}"));
    }
    Ok(())
}
pub(crate) fn one_of(v: &Value, path: &str, values: &[u64]) -> Result<(), String> {
    if !values.contains(&num(v, path)?) {
        return Err(format!("enum {path}"));
    }
    Ok(())
}
pub(crate) fn shape(template: &Value, v: &Value, path: &str) -> Result<(), String> {
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
pub(crate) fn preparse(data: &[u8], token_limit: u32) -> Result<(), String> {
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
            if tokens > token_limit {
                return Err("token cap".into());
            }
        }
    }
    if depth != 0 || in_string {
        return Err("incomplete JSON".into());
    }
    Ok(())
}
