"""Original CPU programs for MMC1 RAM-bank and mirrored-register diagnostics."""
import argparse
from pathlib import Path


def cartridge(case):
    # NES 2.0 MMC1: 512 KiB PRG, 8 KiB CHR RAM, 32 KiB battery RAM.
    rom = bytearray(16 + 512 * 1024)
    rom[:16] = bytes([0x4e, 0x45, 0x53, 0x1a, 32, 0, 0x12, 8, 0, 0, 0x90, 7, 0, 0, 0, 0])
    program = bytearray([0x78, 0xd8, 0xa2, 0xff, 0x9a])  # SEI; CLD; LDX #FF; TXS

    def store(address, value):
        program.extend([0xa9, value, 0x8d, address & 255, address >> 8])

    def serial(address, value):
        for bit in range(5):
            store(address, (value >> bit) & 1)
            program.extend([0xea, 0xea])  # Real CPU cycles, beyond MMC1 write lockout.

    def observe(address, slot):
        program.extend([0xad, address & 255, address >> 8, 0x85, slot])

    store(0x2000, 0)
    store(0x2001, 0)
    if case == 'banked':
        serial(0x8000, 0x0c)  # 8 KiB CHR mode; fixed high 16 KiB PRG bank.
        for bank, value in enumerate([0x11, 0x22, 0x33, 0x44]):
            serial(0xa000, bank << 2)
            store(0x6000, value)
        for bank in range(4):
            serial(0xa000, bank << 2)
            observe(0x6000, 0x10 + bank)
    elif case in ['mirrored', 'mirrored-control']:
        serial(0x8000, 0x1c)  # Separate 4 KiB CHR registers.
        serial(0xa000, 0)
        serial(0xc001 if case == 'mirrored' else 0xc000, 0x10)  # CHR1 selects the upper PRG half.
        observe(0x9000, 0x10)
    else:
        raise ValueError(case)
    store(0x20, 0x80)
    end = 0x8000 + len(program)
    program.extend([0x4c, end & 255, end >> 8])
    assert len(program) < 0x1000
    for bank in range(32):
        start = 16 + bank * 16384
        rom[start:start + len(program)] = program
        rom[start + 0x1000] = bank  # Independent bank identity, not register introspection.
        for vector in [0x3ffa, 0x3ffc, 0x3ffe]:
            rom[start + vector:start + vector + 2] = bytes([0, 0x80])
    return bytes(rom)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('case', choices=['banked', 'mirrored', 'mirrored-control'])
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    args.output.write_bytes(cartridge(args.case))
