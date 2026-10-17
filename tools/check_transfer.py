"""Optional real-wget check: tiny HTTPS loopback fixture, no external services.

Requires GNU wget and openssl. Run in an isolated environment with networking
restricted to loopback. Certificates, subprocesses and files live in a temp dir.
"""
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
import ssl
import subprocess
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import cmip6_downloader as app

BODY = b'offline synthetic fixture\n'


class TransferTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not shutil.which('wget') or not shutil.which('openssl'):
            raise RuntimeError('Install GNU wget and openssl for this optional check')
        cls.temp = tempfile.TemporaryDirectory(prefix='cmip6-tls-')
        cls.addClassCleanup(cls.temp.cleanup)
        cls.root = Path(cls.temp.name)
        cls.cert = cls.root / 'certificate.pem'
        key = cls.root / 'key.pem'
        subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes',
                        '-keyout', str(key), '-out', str(cls.cert), '-days', '1',
                        '-subj', '/CN=localhost', '-addext', 'subjectAltName=DNS:localhost'],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
        cls.requests = []
        cls.release = threading.Event()
        cls.addClassCleanup(cls.release.set)

        class Handler(BaseHTTPRequestHandler):
            def handle(self):
                try:
                    super().handle()
                except (BrokenPipeError, ConnectionResetError, ssl.SSLError):
                    # Expected when the client rejects the fixture certificate.
                    pass

            def log_message(self, *args):
                pass

            def do_GET(self):
                cls.requests.append((self.path, self.headers.get('Range')))
                if self.path == '/search':
                    data = json.dumps({'response': {'numFound': 0, 'docs': []}}).encode()
                    self.send_response(200)
                    self.send_header('Content-Length', str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                    return
                if self.path == '/redirect.nc':
                    self.send_response(302)
                    self.send_header('Location', 'http://localhost:1/should-never-be-requested.nc')
                    self.send_header('Content-Length', '0')
                    self.end_headers()
                    return
                if self.path == '/missing.nc':
                    self.send_error(404)
                    return
                start = 0
                if self.headers.get('Range') and self.path != '/ignore-range.nc':
                    start = int(self.headers['Range'].split('=')[1].split('-')[0])
                self.send_response(206 if start else 200)
                if start:
                    self.send_header('Content-Range', f'bytes {start}-{len(BODY)-1}/{len(BODY)}')
                self.send_header('Content-Length', str(len(BODY) - start))
                self.end_headers()
                try:
                    if self.path == '/slow.nc':
                        self.wfile.write(BODY[:4])
                        self.wfile.flush()
                        cls.release.wait(3)
                    else:
                        self.wfile.write(BODY[start:])
                except (BrokenPipeError, ConnectionResetError, ssl.SSLError):
                    pass

        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        cls.addClassCleanup(cls.server.server_close)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(cls.cert, key)
        cls.server.socket = context.wrap_socket(cls.server.socket, server_side=True)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.addClassCleanup(cls.thread.join, 5)
        cls.addClassCleanup(cls.server.shutdown)
        cls.base = f'https://localhost:{cls.server.server_port}'
        # Wrapper adds an explicit trust root, never disables verification.
        cls.wrapper = cls.root / 'trusted-wget'
        cls.wrapper.write_text('#!/bin/sh\nexec ' + shutil.which('wget') + ' --ca-certificate=' + str(cls.cert) + ' "$@"\n')
        cls.wrapper.chmod(0o700)

    def setUp(self):
        self.work = tempfile.TemporaryDirectory(dir=self.root)
        self.addCleanup(self.work.cleanup)
        self.folder = Path(self.work.name)
        self.stop = threading.Event()
        self.opts = SimpleNamespace(wget=str(self.wrapper), attempts=1, timeout=2)
        self.item = app.File('tiny.nc', self.base + '/tiny.nc', len(BODY), 'sha256', app.hashlib.sha256(BODY).hexdigest())

    def test_resume_uses_range_and_promotion_then_skips(self):
        part = self.folder / 'tiny.nc.part'
        part.write_bytes(BODY[:4])
        app.download_file(self.item, self.folder, self.opts, self.stop)
        self.assertIn(('/tiny.nc', 'bytes=4-'), self.requests)
        self.assertEqual((self.folder / 'tiny.nc').read_bytes(), BODY)
        self.assertFalse(part.exists())
        count = len(self.requests)
        app.download_file(self.item, self.folder, self.opts, self.stop)
        self.assertEqual(len(self.requests), count)

    def test_server_without_range_restarts_and_verifies(self):
        (self.folder / 'tiny.nc.part').write_bytes(BODY[:4])
        app.download_file(replace(self.item, url=self.base + '/ignore-range.nc'), self.folder, self.opts, self.stop)
        self.assertEqual((self.folder / 'tiny.nc').read_bytes(), BODY)

    def test_untrusted_certificate_is_rejected_even_with_personal_config(self):
        self.opts.wget = shutil.which('wget')
        config = self.folder / 'wgetrc'
        config.write_text('check_certificate = off\n')
        with patch.dict(os.environ, {'WGETRC': str(config)}):
            with self.assertRaises(app.DownloadError):
                app.download_file(self.item, self.folder, self.opts, self.stop)
        self.assertFalse((self.folder / 'tiny.nc').exists())

    def test_redirect_404_and_wrong_checksum_never_promote(self):
        for url in ('/redirect.nc', '/missing.nc', '/tiny.nc'):
            folder = self.folder / url.strip('/').replace('.', '-')
            folder.mkdir()
            item = replace(self.item, url=self.base + url, checksum='f' * 64)
            with self.subTest(url=url), self.assertRaises(app.DownloadError):
                app.download_file(item, folder, self.opts, self.stop)
            self.assertFalse((folder / 'tiny.nc').exists())
        self.assertFalse(any('should-never-be-requested' in path for path, _ in self.requests))

    def test_timeout_and_stop_reap_real_wget_and_keep_part(self):
        item = replace(self.item, url=self.base + '/slow.nc')
        for cancel in (False, True):
            folder = self.folder / str(cancel)
            folder.mkdir()
            self.stop = threading.Event()
            self.opts.timeout = 1
            timer = threading.Timer(.3, self.stop.set)
            if cancel:
                timer.start()
            try:
                with self.assertRaises(app.DownloadError):
                    app.download_file(item, folder, self.opts, self.stop)
            finally:
                if cancel:
                    timer.join(2)
            self.assertFalse((folder / 'tiny.nc').exists())
            self.assertEqual((folder / 'tiny.nc.part').read_bytes(), BODY[:4])

    def test_metadata_tls_trust_and_rejection(self):
        # Positive trust is local to this process; no system trust changes.
        with patch.dict(os.environ, {'SSL_CERT_FILE': str(self.cert), 'SSL_CERT_DIR': str(self.folder)}):
            self.assertEqual(app.fetch_json(self.base + '/search', 1, 2)['response']['numFound'], 0)
        with patch.dict(os.environ, {'SSL_CERT_FILE': str(self.folder / 'absent'), 'SSL_CERT_DIR': str(self.folder)}):
            with self.assertRaises(app.DownloadError):
                app.fetch_json(self.base + '/search', 1, 2)


if __name__ == '__main__':
    unittest.main(verbosity=2)
