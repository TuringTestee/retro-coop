//! Bounded ROM-free cartridge-memory fragment, not a complete emulator checkpoint.
//! CPU, PPU, APU and controller codec validation is deliberately not implied.
use tetanes_core::memory::Memory;

const MAGIC: &[u8; 8] = b"D02MEM01";
const HEADER: usize = MAGIC.len() + 32;
pub const LIMIT: usize = 2 * 1024 * 1024;

/// Fingerprint must identify the exact ROM, core, region and memory layout.
/// The complete-checkpoint adapter must derive it from trusted local settings.
pub fn encode(memory: &Memory, fingerprint: &[u8; 32]) -> Result<Vec<u8>, &'static str> {
    let len = HEADER
        .checked_add(memory.ram().len())
        .ok_or("size overflow")?;
    if len > LIMIT {
        return Err("memory fragment over limit");
    }
    let mut result = Vec::with_capacity(len);
    result.extend_from_slice(MAGIC);
    result.extend_from_slice(fingerprint);
    result.extend_from_slice(memory.ram());
    Ok(result)
}

/// Validate length, schema and local identity before writing or allocating.
/// All ranges and ROM remain those of the trusted local Memory instance.
pub fn restore(
    memory: &mut Memory,
    fingerprint: &[u8; 32],
    bytes: &[u8],
) -> Result<(), &'static str> {
    let expected = HEADER
        .checked_add(memory.ram().len())
        .ok_or("size overflow")?;
    if bytes.len() > LIMIT || bytes.len() != expected {
        return Err("invalid memory fragment length");
    }
    if &bytes[..MAGIC.len()] != MAGIC {
        return Err("unknown memory fragment schema");
    }
    if &bytes[MAGIC.len()..HEADER] != fingerprint {
        return Err("incompatible memory fragment");
    }
    memory.ram_mut().copy_from_slice(&bytes[HEADER..]);
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use tetanes_core::memory::{MemoryLayout, Src};

    fn memory() -> Memory {
        let mut layout = MemoryLayout::default();
        layout.prg_rom = 32768;
        layout.chr = 8192;
        layout.prg_ram = 8192;
        layout.ciram = 2048;
        layout.ex_ram = 8192;
        let mut m = Memory::new(layout);
        m.region_mut(Src::PrgRom).fill(0xa5);
        m.region_mut(Src::Chr).fill(0x5a);
        m
    }

    #[test]
    fn fragment_contains_only_mutable_tail_and_preserves_local_rom() {
        let mut source = memory();
        source.ram_mut().fill(0x11);
        let encoded = encode(&source, &[7; 32]).unwrap();
        assert_eq!(encoded.len(), HEADER + source.ram().len());
        assert_eq!(&encoded[HEADER..], source.ram());
        assert!(!encoded.contains(&0xa5));
        assert!(!encoded.contains(&0x5a));
        let mut target = memory();
        restore(&mut target, &[7; 32], &encoded).unwrap();
        assert_eq!(target.ram(), source.ram());
        assert!(target.region_ref(Src::PrgRom).iter().all(|b| *b == 0xa5));
        assert!(target.region_ref(Src::Chr).iter().all(|b| *b == 0x5a));
    }

    #[test]
    fn invalid_fragments_leave_all_memory_untouched() {
        let mut target = memory();
        let valid = encode(&target, &[7; 32]).unwrap();
        let baseline = target.clone();
        let mut cases = vec![
            vec![],
            vec![0; LIMIT + 1],
            valid[..valid.len() - 1].to_vec(),
        ];
        let mut appended = valid.clone();
        appended.push(0);
        cases.push(appended);
        let mut unknown = valid.clone();
        unknown[0] ^= 1;
        cases.push(unknown);
        let mut identity = valid;
        identity[8] ^= 1;
        cases.push(identity);
        for invalid in cases {
            assert!(restore(&mut target, &[7; 32], &invalid).is_err());
            assert_eq!(target.ram(), baseline.ram());
            assert_eq!(
                target.region_ref(Src::PrgRom),
                baseline.region_ref(Src::PrgRom)
            );
        }
    }

    #[test]
    fn upstream_memory_decoder_accepts_small_payload_requesting_large_arena() {
        // Controlled 4 MiB demonstration; never attempt attacker-sized allocation.
        let mut state = serde_json::to_value(memory()).unwrap();
        state["len"] = (4 * 1024 * 1024).into();
        state["ram_start"] = (4 * 1024 * 1024).into();
        state["ram"] = serde_json::json!([]);
        let encoded = serde_json::to_vec(&state).unwrap();
        assert!(encoded.len() < 1024);
        let decoded: Memory = serde_json::from_slice(&encoded).unwrap();
        assert!(decoded.ram().is_empty());
        // This acceptance is the regression evidence for rejecting generic dumps.
        let fragment = encode(&memory(), &[7; 32]).unwrap();
        assert!(restore(&mut memory(), &[7; 32], &encoded).is_err());
        assert!(fragment.len() < LIMIT);
    }
}
