"""Count only IPv4/UDP headers in the isolated research namespace; no payloads."""
import json
import signal
import socket
import struct
import sys
import time
from pathlib import Path

running = True

def stop(_signal, _frame):
    global running
    running = False

signal.signal(signal.SIGTERM, stop)
signal.signal(signal.SIGINT, stop)
started = time.monotonic()
flows = {}
with socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.htons(0x0800)) as capture:
    capture.bind(('lo', 0))
    capture.settimeout(.5)
    Path(sys.argv[2]).write_text('ready\n')
    while running:
        try:
            header, address = capture.recvfrom(42)  # Ethernet + minimal IPv4 + UDP only
        except socket.timeout:
            continue
        if len(header) != 42 or header[14] != 0x45 or header[23] != 17:
            continue
        source, destination = socket.inet_ntoa(header[26:30]), socket.inet_ntoa(header[30:34])
        if source != '10.201.0.1' or destination != source:
            continue
        sport, dport, size = struct.unpack('!HHH', header[34:40])
        key = f'{source}:{sport}>{destination}:{dport}'
        flow = flows.setdefault(key, {'observations': 0, 'udp_bytes': 0})
        flow['observations'] += 1
        flow['udp_bytes'] += size
Path(sys.argv[1]).write_text(json.dumps({'scope': 'IPv4 UDP header observations on namespace lo; no payload retained',
                                        'wall_seconds': time.monotonic()-started, 'flows': flows}, indent=2)+'\n')
