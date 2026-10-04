"""Exercise interrupted official-download recovery with a local HTTP transport."""
import contextlib
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import os
from pathlib import Path
import socket
import ssl
import struct
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

import ci_node


@contextlib.contextmanager
def transport(actions, payload=b'original diagnostic archive'):
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_GET(self):
            requests.append(self.path)
            action = actions[min(len(requests) - 1, len(actions) - 1)]
            if action == 'reset':
                self.connection.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack('ii', 1, 0))
                self.connection.close()
                return
            if action == '503':
                self.send_error(503)
                return
            self.send_response(200)
            self.send_header('Content-Length', str(len(payload)))
            self.end_headers()
            self.wfile.write(payload[:3] if action == 'partial' else payload)
            self.close_connection = True

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    def mapped_open(official_url, **kwargs):
        # Only the test transport maps bytes locally; production URLs/origin checks stay intact.
        response = urlopen(f'http://127.0.0.1:{server.server_port}/archive', **kwargs)
        response.geturl = lambda: official_url
        return response

    try:
        with patch.object(ci_node, 'urlopen', mapped_open):
            yield requests
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


class NodeDownloadTests(unittest.TestCase):
    def test_socket_reset_partial_response_and_http_unavailability_recover(self):
        payload = b'original diagnostic archive'
        for failure in ('reset', 'partial', '503'):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as temp:
                archive = Path(temp) / 'node-v24.13.1-linux-x64.tar.xz'
                sums = Path(temp) / 'SHASUMS256.txt'
                sums.write_text(f'{hashlib.sha256(payload).hexdigest()}  {archive.name}\n')
                with transport([failure, 'ok'], payload) as requests:
                    ci_node.download('https://nodejs.org/dist/v24.13.1/' + archive.name, archive, time.time() + 5)
                self.assertEqual(len(requests), 2)
                self.assertEqual(archive.read_bytes(), payload)
                self.assertEqual(ci_node.verify_archive(archive, sums), hashlib.sha256(payload).hexdigest())

    def test_only_three_attempts_and_short_remaining_deadline_never_waits_for_retry(self):
        for remaining, expected in ((5, 3), (0.1, 1)):
            with self.subTest(remaining=remaining), tempfile.TemporaryDirectory() as temp:
                with transport(['reset']) as requests:
                    with self.assertRaises((ConnectionResetError, URLError)):
                        ci_node.download('https://nodejs.org/archive', Path(temp) / 'archive', time.time() + remaining)
                self.assertEqual(len(requests), expected)

    def test_global_timeout_certificate_failure_and_permanent_http_error_are_terminal(self):
        failures = [TimeoutError('global deadline'), URLError(ssl.SSLCertVerificationError('invalid certificate')),
                    HTTPError('https://nodejs.org/archive', 404, 'missing', {}, None)]
        with tempfile.TemporaryDirectory() as temp:
            for failure in failures:
                with self.subTest(failure=failure), patch.object(ci_node, 'urlopen', side_effect=failure) as opened:
                    with self.assertRaises(type(failure)):
                        ci_node.download('https://nodejs.org/archive', Path(temp) / 'archive', time.time() + 5)
                    self.assertEqual(opened.call_count, 1)

    def test_corruption_remains_terminal_before_extraction_execution_and_path_publication(self):
        version = (Path(ci_node.__file__).resolve().parents[2] / ".node-version").read_text().strip()
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'github-path'
            path.write_text('sentinel\n')

            def damaged_download(_url, destination, _deadline):
                if destination.name == 'SHASUMS256.txt':
                    destination.write_text(f'{hashlib.sha256(b"original").hexdigest()}  node-v{version}-linux-x64.tar.xz\n')
                else:
                    destination.write_bytes(b'damaged')

            with patch.dict(os.environ, RUNNER_TEMP=temp, GITHUB_PATH=str(path)), \
                    patch.object(ci_node.platform, 'machine', return_value='x86_64'), \
                    patch.object(ci_node.platform, 'system', return_value='Linux'), \
                    patch.object(ci_node, 'download', side_effect=damaged_download), \
                    patch.object(ci_node.tarfile, 'open') as extracted, \
                    patch.object(ci_node.subprocess, 'check_output') as executed:
                with self.assertRaisesRegex(ValueError, 'checksum mismatch'):
                    ci_node.install(time.time() + 5)
                extracted.assert_not_called()
                executed.assert_not_called()
            self.assertEqual(path.read_text(), 'sentinel\n')
            self.assertEqual(list(Path(temp).iterdir()), [path])


if __name__ == '__main__':
    unittest.main()
