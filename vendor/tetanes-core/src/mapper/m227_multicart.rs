//! Address-latched multicarts and battery-backed RPG boards (mapper 227).
//!
//! Hardware reference: <https://www.nesdev.org/wiki/INES_Mapper_227>.
//! Extended NES 2.0 submappers with solder-pad reads are not implemented.
#![allow(missing_docs)]

use crate::{
    cart::Cart,
    common::ResetKind,
    mapper::{self, Map, Mapper},
    memory::{Memory, Src},
    ppu::Mirroring,
};
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
#[must_use]
pub struct Multicart227 {
    pub latch: u16,
    pub multicart: bool,
}

impl Multicart227 {
    pub fn load(cart: &mut Cart) -> Result<Mapper, mapper::Error> {
        let mut board = Self {
            latch: 0,
            // Legacy iNES distinguishes multicarts from the writable-CHR/WRAM
            // RPG variant through the battery flag, not a particular ROM identity.
            multicart: !cart.battery_backed(),
        };
        board.update_banks(&mut cart.memory);
        Ok(board.into())
    }
}

impl Map for Multicart227 {
    fn mirroring(&self) -> Mirroring {
        if self.latch & 2 == 0 { Mirroring::Vertical } else { Mirroring::Horizontal }
    }

    fn write_register(&mut self, memory: &mut Memory, addr: u16, _val: u8) {
        if addr >= 0x8000 {
            // Only the address lines drive the latch. Data and high address
            // mirrors have no effect on the base board.
            self.latch = addr & 0x03ff;
            self.update_banks(memory);
        }
    }

    fn update_banks(&mut self, memory: &mut Memory) {
        let bank = ((self.latch >> 2) & 0x1f) | ((self.latch >> 3) & 0x20);
        let paired = self.latch & 1 != 0;
        let nrom = self.latch & 0x80 != 0;
        let low = if paired { bank & !1 } else { bank };
        let high = if nrom {
            if paired { low + 1 } else { bank }
        } else if self.latch & 0x200 != 0 {
            bank | 7
        } else {
            bank & !7
        };
        memory.map_prg(0x8000, 16 * 1024, i32::from(low), Src::PrgRom);
        memory.map_prg(0xc000, 16 * 1024, i32::from(high), Src::PrgRom);
        if self.multicart {
            memory.unmap_prg(0x6000, 8 * 1024);
        } else {
            memory.map_prg(0x6000, 8 * 1024, 0, Src::PrgRam);
        }
        memory.map_chr(0, 8 * 1024, 0, Src::Chr);
        memory.set_chr_writable(0, 8 * 1024, !(self.multicart && nrom));
        memory.set_mirroring(self.mirroring());
    }

    fn reset(&mut self, _kind: ResetKind) {
        self.latch = 0;
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::mapper::test_utils::{page_indexed_cart, prg_peek, write};

    fn board(battery: bool) -> (Mapper, Cart) {
        let mut cart = page_indexed_cart(1024 * 1024, 8 * 1024, 0);
        cart.header.flags = if battery { 2 } else { 0 };
        for (bank, bytes) in cart.memory.region_mut(Src::PrgRom).chunks_mut(16 * 1024).enumerate() {
            bytes.fill(bank as u8);
        }
        let mapper = Multicart227::load(&mut cart).unwrap();
        (mapper, cart)
    }

    #[test]
    fn all_inner_outer_and_prg_modes_follow_the_address_lines() {
        let (mut mapper, mut cart) = board(false);
        for outer in 0..8u16 {
            for inner in 0..8u16 {
                for mode in 0..8u16 {
                    let addr = 0x8000 | ((outer & 4) << 6) | ((outer & 3) << 5)
                        | (inner << 2) | ((mode & 4) << 7) | ((mode & 2) << 6) | (mode & 1);
                    write(&mut mapper, &mut cart, addr, 0xff);
                    let bank = (outer * 8 + inner) as u8;
                    let low = if mode & 1 != 0 { bank & !1 } else { bank };
                    let high = match (mode & 2 != 0, mode & 1 != 0, mode & 4 != 0) {
                        (true, true, _) => low + 1,
                        (true, false, _) => bank,
                        (false, _, true) => outer as u8 * 8 + 7,
                        (false, _, false) => outer as u8 * 8,
                    };
                    assert_eq!(prg_peek(&mapper, &cart, 0x8000), low, "${addr:04x}");
                    assert_eq!(prg_peek(&mapper, &cart, 0xc000), high, "${addr:04x}");
                }
            }
        }
    }

    #[test]
    fn chr_protection_tracks_multicart_mode_but_not_battery_rpg_boards() {
        for battery in [false, true] {
            let (mut mapper, mut cart) = board(battery);
            cart.memory.chr_write(0x123, 0x33);
            write(&mut mapper, &mut cart, 0x8080, 0);
            cart.memory.chr_write(0x123, 0x66);
            assert_eq!(cart.memory.chr_peek(0x123), if battery { 0x66 } else { 0x33 });
            write(&mut mapper, &mut cart, 0x8000, 0);
            cart.memory.chr_write(0x123, 0x99);
            assert_eq!(cart.memory.chr_peek(0x123), 0x99);
            cart.memory.prg_write(0x6000, 0x42);
            assert_eq!(cart.memory.prg_peek(0x6000), if battery { 0x42 } else { 0 });
        }
    }

    #[test]
    fn reset_mirroring_register_decode_and_state_rebuild() {
        let (mut mapper, mut cart) = board(false);
        assert_eq!(prg_peek(&mapper, &cart, 0xc000), 0);
        write(&mut mapper, &mut cart, 0x818b, 0);
        assert_eq!(mapper.mirroring(), Mirroring::Horizontal);
        let before = cart.memory.prg_peek(0x8000);
        write(&mut mapper, &mut cart, 0x7fff, 0xff);
        assert_eq!(cart.memory.prg_peek(0x8000), before);
        write(&mut mapper, &mut cart, 0xc18b, 0xff);
        assert_eq!(cart.memory.prg_peek(0x8000), before, "data and high mirrors ignored");
        let bytes = bincode::serde::encode_to_vec(&mapper, bincode::config::standard()).unwrap();
        let (mut restored, _): (Mapper, usize) = bincode::serde::decode_from_slice(&bytes, bincode::config::standard()).unwrap();
        cart.memory.unmap_prg(0x8000, 32 * 1024);
        restored.update_banks(&mut cart.memory);
        assert_eq!(cart.memory.prg_peek(0x8000), before);
        cart.memory.chr_write(0x123, 0x77);
        assert_ne!(cart.memory.chr_peek(0x123), 0x77, "restored CHR protection");
        for kind in [ResetKind::Soft, ResetKind::Hard] {
            restored.reset(kind);
            restored.update_banks(&mut cart.memory);
            assert_eq!(cart.memory.prg_peek(0x8000), 0);
            assert_eq!(cart.memory.prg_peek(0xc000), 0);
            assert_eq!(restored.mirroring(), Mirroring::Vertical);
            cart.memory.chr_write(0x123, 0x77);
            assert_eq!(cart.memory.chr_peek(0x123), 0x77);
        }
    }
}
