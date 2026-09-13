"""Generate an original NROM controller diagnostic; no third-party ROM bytes.

The 6502 program polls both controller ports once per vblank, stores their
serial button bytes at $00/$01, increments $02 and changes the backdrop.
This is a test fixture, not a replacement featured game.
"""
from pathlib import Path
import sys

def build():
    code = bytearray()
    labels = {}
    fixups = []
    def emit(*values): code.extend(values)
    def label(name): labels[name] = len(code)
    def branch(op, target):
        emit(op, 0); fixups.append((len(code)-1, target, True))
    def jump(target):
        emit(0x4c, 0, 0); fixups.append((len(code)-2, target, False))
    label('reset')
    emit(0x78, 0xd8, 0xa2, 0xff, 0x9a)  # SEI; CLD; LDX #$ff; TXS
    emit(0xa9, 0x00, 0x8d, 0x00, 0x20, 0x8d, 0x01, 0x20)  # disable NMI/rendering
    emit(0x85, 0x00, 0x85, 0x01, 0x85, 0x02)
    emit(0xa9, 0x40, 0x8d, 0x17, 0x40)  # inhibit APU frame IRQ
    emit(0xa9, 0x01, 0x8d, 0x15, 0x40)  # enable pulse 1
    emit(0xa9, 0xbf, 0x8d, 0x00, 0x40)  # duty 2, halt length, constant volume 15
    emit(0xa9, 0xfd, 0x8d, 0x02, 0x40, 0xa9, 0x08, 0x8d, 0x03, 0x40)
    label('frame')
    emit(0x2c, 0x02, 0x20)  # BIT PPUSTATUS
    branch(0x10, 'frame')  # BPL: wait for vblank
    emit(0xa9, 0x01, 0x8d, 0x16, 0x40, 0x4a, 0x8d, 0x16, 0x40)  # latch both ports
    emit(0xa2, 0x08)
    label('buttons')
    emit(0xad, 0x16, 0x40, 0x4a, 0x26, 0x00)  # read P1 -> carry -> ROL $00
    emit(0xad, 0x17, 0x40, 0x4a, 0x26, 0x01)  # read P2 -> carry -> ROL $01
    emit(0xca); branch(0xd0, 'buttons')
    emit(0xe6, 0x02)  # progress counter
    emit(0xa9, 0x3f, 0x8d, 0x06, 0x20, 0xa9, 0x00, 0x8d, 0x06, 0x20)
    emit(0xa5, 0x00, 0x45, 0x01, 0x29, 0x0f, 0x8d, 0x07, 0x20)  # backdrop from input
    # With rendering disabled, PPUADDR in palette RAM selects the displayed entry.
    # PPUDATA incremented it to $3f01; return to the entry just written.
    emit(0xa9, 0x3f, 0x8d, 0x06, 0x20, 0xa9, 0x00, 0x8d, 0x06, 0x20)
    jump('frame')
    label('interrupt'); emit(0x40)  # RTI
    for offset, name, relative in fixups:
        target = labels[name]
        if relative:
            delta = target - (offset + 1)
            assert -128 <= delta <= 127
            code[offset] = delta & 255
        else:
            code[offset:offset+2] = (0x8000+target).to_bytes(2,'little')
    prg = code + bytes([0xea]) * (16384-len(code))
    for offset, name in [(0x3ffa,'interrupt'),(0x3ffc,'reset'),(0x3ffe,'interrupt')]:
        prg[offset:offset+2]=(0x8000+labels[name]).to_bytes(2,'little')
    return b'NES\x1a'+bytes([1,1])+bytes(10)+prg+bytes(8192)

if __name__ == '__main__':
    Path(sys.argv[1]).write_bytes(build())
