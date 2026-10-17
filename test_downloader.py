"""Offline regressions. Every test denies external sockets and real wget by default."""
import contextlib
from dataclasses import replace
import io
from http.client import IncompleteRead
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from urllib.error import URLError
from urllib.parse import parse_qs, urlsplit

import cmip6_downloader as app

PAYLOAD = b'tiny synthetic data\n'
ITEM = app.File('sample.nc', 'https://data.example/sample.nc', len(PAYLOAD), 'sha256',
                app.hashlib.sha256(PAYLOAD).hexdigest())


def options(**changes):
    values = dict(workers=2, attempts=2, timeout=1, max_records=10000,
                  search_url='https://search.example/search', wget='/fake/wget')
    values.update(changes)
    return SimpleNamespace(**values)


def doc(item=ITEM, identifier='file-1'):
    return dict(id=identifier, url=[item.url + '|application/netcdf|HTTPServer'],
                size=item.size, checksum=[item.checksum], checksum_type=[item.checksum_type])


def response(docs, count=None):
    return {'response': {'numFound': len(docs) if count is None else count, 'docs': docs}}


class OfflineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.stop = threading.Event()
        self.stdout = self.enterContext(contextlib.redirect_stdout(io.StringIO()))
        self.stderr = self.enterContext(contextlib.redirect_stderr(io.StringIO()))
        self.enterContext(patch.object(socket.socket, 'connect', side_effect=AssertionError('Network forbidden')))
        self.enterContext(patch.object(socket, 'create_connection', side_effect=AssertionError('Network forbidden')))
        self.enterContext(patch.object(app.subprocess, 'Popen', side_effect=AssertionError('Real process forbidden')))

    def test_import_has_no_process_network_or_file_effects(self):
        code = '''
import builtins, multiprocessing, pathlib, socket, subprocess, sys
sys.dont_write_bytecode = True
sys.path.insert(0, sys.argv[1])
def denied(*a, **kw): raise AssertionError('import side effect')
builtins.open = denied
multiprocessing.Manager = denied
multiprocessing.Pool = denied
socket.socket.connect = denied
subprocess.Popen = denied
import cmip6_downloader
assert not list(pathlib.Path('.').iterdir())
'''
        # Only this isolated import probe may launch Python, never wget.
        with patch.object(app.subprocess, 'Popen', new=ORIGINAL_POPEN):
            result = subprocess.run([sys.executable, '-B', '-c', code, str(Path(app.__file__).parent)],
                                    cwd=self.folder, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr.decode())

    def test_cli_empty_filters_fail_without_network(self):
        with self.assertRaises(SystemExit) as error:
            app.get_params(['--variable_id', ' '])
        self.assertEqual(error.exception.code, 2)
        self.assertEqual(list(self.folder.iterdir()), [])

    def test_interactive_empty_and_valid(self):
        with patch('builtins.input', return_value=''):
            with self.assertRaises(SystemExit):
                app.get_params([])
        with patch('builtins.input', side_effect=['tas', 'mon', '', '']):
            _, filters = app.get_params([])
        self.assertEqual(filters, {'variable_id': 'tas', 'frequency': 'mon'})

    def test_cli_bounds_controls_and_unknown_flags(self):
        for args in (['--workers', '0'], ['--workers', '9'], ['--attempts', '0'],
                     ['--attempts', '6'], ['--timeout', '0'], ['--max-records', '100001'],
                     ['--typo', 'tas'], ['--frequency', 'a\nb']):
            with self.subTest(args=args), self.assertRaises(SystemExit):
                app.get_params(['--variable_id', 'tas'] + args)

    def test_deterministic_contained_output_for_hostile_filter(self):
        filters = {'variable_id': '../../a; $(touch bad)', 'frequency': 'mon'}
        folder = app.output_folder(self.folder, filters)
        self.assertEqual(folder.parent, self.folder)
        self.assertEqual(folder, app.output_folder(self.folder, dict(reversed(list(filters.items())))))
        self.assertNotEqual(folder, app.output_folder(self.folder, dict(filters, frequency='day')))
        self.assertNotIn('/', folder.name)
        self.assertLess(len(folder.name), 64)

    def test_url_policy_and_redirect_downgrade(self):
        for url in ('http://example/a.nc', 'file:///tmp/a.nc', 'https://u:p@example/a.nc',
                    'https://example/a.nc#frag', 'https://example/a\n.nc', 'https://example:bad/a.nc'):
            with self.subTest(url=url), self.assertRaises((app.DownloadError, ValueError)):
                app.https_url(url)
        with self.assertRaises(app.DownloadError):
            app.HTTPSRedirectHandler().redirect_request(None, None, 302, '', {}, 'http://bad.example/')

    def test_metadata_retry_bounded_closes_response_and_sets_timeout(self):
        body = io.BytesIO(json.dumps(response([])).encode())
        opener = SimpleNamespace(open=unittest.mock.Mock(side_effect=[URLError('offline'), body]))
        with patch.object(app.urllib.request, 'build_opener', return_value=opener), patch.object(app.time, 'sleep') as sleep:
            self.assertEqual(app.fetch_json('https://search.example/', 2, 7), response([]))
        self.assertTrue(body.closed)
        self.assertEqual(opener.open.call_count, 2)
        self.assertEqual(opener.open.call_args.kwargs['timeout'], 7)
        sleep.assert_called_once_with(1)

    def test_metadata_exhaustion_and_bad_json(self):
        opener = SimpleNamespace(open=unittest.mock.Mock(side_effect=URLError('offline')))
        with patch.object(app.urllib.request, 'build_opener', return_value=opener), patch.object(app.time, 'sleep'):
            with self.assertRaisesRegex(app.DownloadError, 'bounded attempts'):
                app.fetch_json('https://search.example/', 3, 1)
        self.assertEqual(opener.open.call_count, 3)
        for raw in (b'not json', b'x' * (app.MAX_RESPONSE_BYTES + 1)):
            opener.open.side_effect = None
            opener.open.return_value = io.BytesIO(raw)
            with patch.object(app.urllib.request, 'build_opener', return_value=opener):
                with self.assertRaises(app.DownloadError):
                    app.fetch_json('https://search.example/', 1, 1)

    def test_truncated_metadata_retries_and_closes_response(self):
        broken = unittest.mock.MagicMock()
        broken.__enter__.return_value = broken
        broken.read.side_effect = IncompleteRead(b'prefix', 20)
        good = io.BytesIO(json.dumps(response([])).encode())
        opener = SimpleNamespace(open=unittest.mock.Mock(side_effect=[broken, good]))
        with patch.object(app.urllib.request, 'build_opener', return_value=opener), patch.object(app.time, 'sleep'):
            self.assertEqual(app.fetch_json('https://search.example/', 2, 1), response([]))
        broken.__exit__.assert_called_once()
        self.assertTrue(good.closed)

    def test_paginate_and_encode_dataset_identifier(self):
        docs = [{'id': 'dataset&a|node'}, {'id': 'other'}]
        with patch.object(app, 'PAGE_SIZE', 1), patch.object(app, 'fetch_json', side_effect=[response(docs[:1], 2), response(docs[1:], 2)]) as fetch:
            self.assertEqual(app.search(options().search_url, {'dataset_id': docs[0]['id']}, options()), docs)
        query = parse_qs(urlsplit(fetch.call_args.args[0]).query)
        self.assertEqual(query['dataset_id'], ['dataset&a|node'])
        self.assertEqual(query['offset'], ['1'])

    def test_incomplete_changing_repeated_and_over_limit_pages_fail(self):
        for pages in ([response([], 1)], [response([{'id': 'a'}], 10001)],
                      [response([{'id': 'a'}], 2), response([{'id': 'a'}], 2)],
                      [response([{'id': 'a'}], 2), response([{'id': 'b'}], 3)],
                      [{'response': {'docs': []}}], [response([{}])]):
            with self.subTest(pages=pages), patch.object(app, 'fetch_json', side_effect=pages):
                with self.assertRaises(app.DownloadError):
                    app.search(options().search_url, {}, options())

    def test_file_metadata_validation(self):
        self.assertEqual(app.file_from_doc(doc()), ITEM)
        for changes in ({'size': -1}, {'size': True}, {'size': 0}, {'checksum_type': ['unknown']},
                        {'checksum': ['invalid']}, {'url': 'not a list'},
                        {'url': ['http://data.example/a.nc|netcdf|HTTPServer']},
                        {'url': ['https://data.example/%2Foutside.nc|netcdf|HTTPServer']},
                        {'url': ['https://data.example/..%5Ca.nc|netcdf|HTTPServer']},
                        {'url': ['https://data.example/a.nc;bad|netcdf|HTTPServer']}):
            with self.subTest(changes=changes), self.assertRaises(app.DownloadError):
                app.file_from_doc(dict(doc(), **changes))

    def test_legacy_checksums_and_file_metadata_budget(self):
        for algorithm in ('md5', 'sha1'):
            checksum = app.hashlib.new(algorithm, PAYLOAD, usedforsecurity=False).hexdigest()
            item = replace(ITEM, checksum_type=algorithm, checksum=checksum)
            self.assertEqual(app.file_from_doc(doc(item)), item)
            path = self.folder / algorithm
            path.write_bytes(PAYLOAD)
            self.assertTrue(app.complete(path, item, self.stop))
        datasets = [{'id': 'a', 'number_of_files': 1}, {'id': 'b', 'number_of_files': 1}]
        with patch.object(app, 'search', side_effect=[datasets, [doc()]]) as search:
            with self.assertRaisesRegex(app.DownloadError, 'Total file metadata'):
                app.collect_files({}, options(max_records=1))
        self.assertEqual(search.call_count, 2)

    def test_duplicates_collapse_and_conflicts_fail_before_transfers(self):
        datasets = [{'id': 'd', 'number_of_files': 2}]
        for second, expected_error in ((doc(identifier='replica'), False),
                                       (doc(replace(ITEM, checksum='f' * 64), 'conflict'), True),
                                       (doc(replace(ITEM, name='SAMPLE.nc', url='https://other.example/SAMPLE.nc'), 'case'), True)):
            with patch.object(app, 'search', side_effect=[datasets, [doc(), second]]):
                if expected_error:
                    with self.assertRaises(app.DownloadError):
                        app.collect_files({'variable_id': 'tas'}, options())
                else:
                    self.assertEqual(app.collect_files({'variable_id': 'tas'}, options()), [ITEM])
        with patch.object(app, 'search', side_effect=[[{'id': 'd', 'number_of_files': 2}], [doc()]]):
            with self.assertRaises(app.DownloadError):
                app.collect_files({}, options())

    def test_file_count_is_not_completion_and_existing_invalid_is_preserved(self):
        final = self.folder / ITEM.name
        final.write_bytes(b'x' * ITEM.size)
        (self.folder / 'unrelated.nc').write_bytes(PAYLOAD)
        with patch.object(app, 'wget_attempt') as run:
            with self.assertRaisesRegex(app.DownloadError, 'Existing file failed'):
                app.download_file(ITEM, self.folder, options(), self.stop)
        run.assert_not_called()
        self.assertEqual(final.read_bytes(), b'x' * ITEM.size)

    def test_verified_existing_file_skips_wget(self):
        (self.folder / ITEM.name).write_bytes(PAYLOAD)
        with patch.object(app, 'wget_attempt') as run:
            self.assertIn('Verified existing', app.download_file(ITEM, self.folder, options(), self.stop))
        run.assert_not_called()

    def test_resume_and_literal_wget_arguments(self):
        folder = self.folder / 'space ; shell $(ignored)'
        folder.mkdir()
        partial = folder / (ITEM.name + '.part')
        partial.write_bytes(PAYLOAD[:4])
        item = replace(ITEM, url=ITEM.url + '?literal=one&two=$(bad)')
        def resume(command, timeout, stop):
            self.assertEqual(partial.read_bytes(), PAYLOAD[:4])
            self.assertEqual(command[-2:], ['--', item.url])
            self.assertIn('--output-document=' + str(partial), command)
            for flag in ('--continue', '--no-config', '--no-netrc', '--no-hsts', '--no-iri', '--max-redirect=0', '--tries=1'):
                self.assertIn(flag, command)
            self.assertNotIn('--no-check-certificate', command)
            partial.write_bytes(PAYLOAD)
            return 0
        with patch.object(app, 'wget_attempt', side_effect=resume):
            app.download_file(item, folder, options(), self.stop)
        self.assertFalse(partial.exists())
        self.assertEqual((folder / ITEM.name).read_bytes(), PAYLOAD)

    def test_success_exit_with_short_or_corrupt_body_never_promotes(self):
        for payload in (b'short', b'x' * ITEM.size):
            partial = self.folder / (ITEM.name + '.part')
            def transfer(*args):
                partial.write_bytes(payload)
                return 0
            with patch.object(app, 'wget_attempt', side_effect=transfer):
                with self.assertRaises(app.DownloadError):
                    app.download_file(ITEM, self.folder, options(attempts=1), self.stop)
            self.assertFalse((self.folder / ITEM.name).exists())
            self.assertEqual(partial.read_bytes(), payload)
            partial.unlink()

    def test_failed_transfer_retains_prefix_and_retries_independent_of_workers(self):
        for workers in (1, 8):
            partial = self.folder / (ITEM.name + '.part')
            def fail(*args):
                partial.write_bytes(PAYLOAD[:4])
                return 4
            with patch.object(app, 'wget_attempt', side_effect=fail) as run, patch.object(self.stop, 'wait', return_value=False):
                with self.assertRaises(app.DownloadError):
                    app.download_file(ITEM, self.folder, options(workers=workers, attempts=3), self.stop)
            self.assertEqual(run.call_count, 3)
            self.assertEqual(partial.read_bytes(), PAYLOAD[:4])

    def test_complete_partial_promotes_without_transfer(self):
        (self.folder / (ITEM.name + '.part')).write_bytes(PAYLOAD)
        with patch.object(app, 'wget_attempt') as run:
            app.download_file(ITEM, self.folder, options(), self.stop)
        run.assert_not_called()
        self.assertEqual((self.folder / ITEM.name).read_bytes(), PAYLOAD)

    def test_symlink_directory_and_hardlink_files_are_refused(self):
        outside = self.folder / 'outside'
        outside.write_bytes(b'keep')
        partial = self.folder / (ITEM.name + '.part')
        for kind in ('symlink', 'directory', 'hardlink'):
            if kind == 'symlink':
                partial.symlink_to(outside)
            elif kind == 'directory':
                partial.mkdir()
            else:
                os.link(outside, partial)
            with self.assertRaises(app.DownloadError):
                app.download_file(ITEM, self.folder, options(), self.stop)
            partial.rmdir() if kind == 'directory' else partial.unlink()
        self.assertEqual(outside.read_bytes(), b'keep')

    def test_output_lock_rejects_concurrent_run_and_releases_on_error(self):
        with app.output_lock(self.folder):
            with self.assertRaisesRegex(app.DownloadError, 'Another download'):
                with app.output_lock(self.folder):
                    self.fail('second lock acquired')
        with self.assertRaises(RuntimeError):
            with app.output_lock(self.folder):
                raise RuntimeError('synthetic')
        with app.output_lock(self.folder):
            pass

    def test_manifest_symlink_refused_and_atomic_content(self):
        app.write_manifest(self.folder, {'variable_id': 'tas'}, [ITEM])
        self.assertEqual(json.loads((self.folder / 'manifest.json').read_text())['files'][0]['size'], ITEM.size)
        target = self.folder / 'outside'
        target.write_text('keep')
        (self.folder / 'manifest.json.tmp').symlink_to(target)
        with self.assertRaises(app.DownloadError):
            app.write_manifest(self.folder, {}, [ITEM])
        self.assertEqual(target.read_text(), 'keep')

    def test_pool_bounds_propagates_failure_and_finishes_other_files(self):
        state = {'active': 0, 'peak': 0, 'seen': 0}
        lock = threading.Lock()
        def download(item, *args):
            with lock:
                state['active'] += 1
                state['peak'] = max(state['peak'], state['active'])
                state['seen'] += 1
            time.sleep(.01)
            with lock:
                state['active'] -= 1
            if item.name == 'bad.nc':
                raise app.DownloadError('synthetic failure')
            return 'verified'
        files = [replace(ITEM, name='bad.nc')] + [replace(ITEM, name=str(i) + '.nc') for i in range(8)]
        with patch.object(app, 'download_file', side_effect=download):
            self.assertEqual(app.download_all(files, self.folder, options(workers=2), self.stop), 1)
        self.assertEqual(state['seen'], 9)
        self.assertEqual(state['peak'], 2)
        self.assertIn('synthetic failure', self.stderr.getvalue())

    def test_interrupt_sets_stop_and_shuts_down_workers(self):
        with patch.object(app, 'wait', side_effect=KeyboardInterrupt), patch.object(app, 'download_file', return_value='done'):
            with self.assertRaises(KeyboardInterrupt):
                app.download_all([ITEM] * 4, self.folder, options(), self.stop)
        self.assertTrue(self.stop.is_set())

    def test_timeout_and_cancellation_reap_child(self):
        process = unittest.mock.MagicMock()
        process.__enter__.return_value = process
        process.poll.return_value = None
        process.wait.side_effect = [subprocess.TimeoutExpired('wget', 2), 0]
        with patch.object(app.subprocess, 'Popen', return_value=process), patch.object(app.time, 'monotonic', side_effect=[0, 2]):
            with self.assertRaisesRegex(app.DownloadError, 'timed out'):
                app.wget_attempt(['wget'], 1, self.stop)
        process.terminate.assert_called_once()
        process.kill.assert_called_once()
        self.assertEqual(process.wait.call_count, 2)
        self.stop.set()
        process.reset_mock()
        process.wait.side_effect = None
        with patch.object(app.subprocess, 'Popen', return_value=process):
            with self.assertRaisesRegex(app.DownloadError, 'Interrupted'):
                app.wget_attempt(['wget'], 1, self.stop)
        process.terminate.assert_called_once()

    def test_main_offline_journey_dry_run_failure_and_resume(self):
        args = ['--variable_id', 'tas', '--output', str(self.folder)]
        def search(url, params, opts):
            return ([{'id': 'dataset', 'number_of_files': 1}]
                    if params['type'] == 'Dataset' else [doc()])
        def transfer(command, timeout, stop):
            Path(next(arg.split('=', 1)[1] for arg in command if arg.startswith('--output-document='))).write_bytes(PAYLOAD)
            return 0
        with patch.object(app.shutil, 'which', return_value='/fake/wget'), patch.object(app, 'search', side_effect=search), patch.object(app, 'wget_attempt', side_effect=transfer) as run:
            self.assertEqual(app.main(args + ['--dry-run']), 0)
            self.assertEqual(list(self.folder.iterdir()), [])
            self.assertEqual(app.main(args), 0)
            self.assertEqual(app.main(args), 0)
            self.assertEqual(run.call_count, 1)
        self.assertIn('1 verified, 0 failed', self.stdout.getvalue())
        with patch.object(app.shutil, 'which', return_value='/fake/wget'), patch.object(app, 'collect_files', return_value=[ITEM]), patch.object(app, 'download_all', return_value=1):
            self.assertEqual(app.main(args), 1)

    def test_missing_wget_empty_search_and_search_failure_exits(self):
        args = ['--variable_id', 'tas', '--output', str(self.folder)]
        with patch.object(app.shutil, 'which', return_value=None):
            self.assertEqual(app.main(args), 1)
        with patch.object(app, 'collect_files', return_value=[]):
            self.assertEqual(app.main(args + ['--dry-run']), 0)
        with patch.object(app, 'collect_files', side_effect=app.DownloadError('bad metadata')):
            self.assertEqual(app.main(args + ['--dry-run']), 1)
        with patch.object(app, 'collect_files', side_effect=KeyboardInterrupt):
            self.assertEqual(app.main(args + ['--dry-run']), 130)
        self.assertEqual(list(self.folder.iterdir()), [])


ORIGINAL_POPEN = subprocess.Popen

if __name__ == '__main__':
    unittest.main()
