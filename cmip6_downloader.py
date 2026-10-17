"""Search ESGF metadata and fetch verified CMIP6 files. Importing has no side effects."""

import argparse
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from contextlib import contextmanager
from dataclasses import asdict, dataclass
import fcntl
import hashlib
from http.client import HTTPException
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import threading
import time
from urllib.error import URLError
from urllib.parse import unquote, urlencode, urlsplit
import urllib.request

VERSION = '5.0.0'
SEARCH_URL = 'https://metagrid.esgf-west.org/proxy/search'
FACETS = (
    'mip_era', 'activity_id', 'model_cohort', 'product', 'source_id',
    'institution_id', 'source_type', 'nominal_resolution', 'experiment_id',
    'sub_experiment_id', 'variant_label', 'grid_label', 'table_id', 'frequency',
    'realm', 'variable_id', 'cf_standard_name', 'data_node',
)
PAGE_SIZE = 500
MAX_RESPONSE_BYTES = 4 * 1024 * 1024


class DownloadError(Exception):
    """An actionable search, validation or transfer failure."""


@dataclass(frozen=True)
class File:
    name: str
    url: str
    size: int
    checksum_type: str
    checksum: str


def https_url(url):
    if not isinstance(url, str) or any(ord(c) <= 32 or ord(c) == 127 for c in url):
        raise DownloadError('URL contains whitespace or control characters')
    parsed = urlsplit(url)
    if (parsed.scheme != 'https' or not parsed.hostname or parsed.username is not None
            or parsed.password is not None or parsed.fragment):
        raise DownloadError('Only credential-free HTTPS URLs without fragments are supported')
    # Validate port syntax now, before opening a connection.
    try:
        parsed.port
    except ValueError as exc:
        raise DownloadError('Invalid URL port') from exc
    return parsed


class HTTPSRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        https_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch_json(url, attempts, timeout):
    https_url(url)
    opener = urllib.request.build_opener(HTTPSRedirectHandler())
    for attempt in range(attempts):
        try:
            with opener.open(url, timeout=timeout) as response:
                raw = response.read(MAX_RESPONSE_BYTES + 1)
            if len(raw) > MAX_RESPONSE_BYTES:
                raise DownloadError('Metadata response exceeds 4 MiB; narrow the search')
            return json.loads(raw)
        except (URLError, TimeoutError, OSError, HTTPException) as exc:
            if attempt + 1 == attempts:
                raise DownloadError('Metadata request failed after bounded attempts; check endpoint/TLS') from exc
            time.sleep(min(2 ** attempt, 4))
        except (ValueError, UnicodeError) as exc:
            raise DownloadError('Metadata response is not valid JSON') from exc


def integer(value, label):
    if isinstance(value, bool) or not re.fullmatch(r'[0-9]+', str(value)):
        raise DownloadError('Invalid metadata ' + label)
    return int(value)


def search(endpoint, params, options):
    """Paginate fully or fail; never quietly return a truncated search."""
    offset = 0
    total = None
    records = []
    ids = set()
    while total is None or offset < total:
        query = dict(params, offset=offset, limit=PAGE_SIZE, format='application/solr+json')
        data = fetch_json(endpoint + '?' + urlencode(query), options.attempts, options.timeout)
        try:
            response = data['response']
            count = integer(response['numFound'], 'numFound')
            docs = response['docs']
        except (KeyError, TypeError) as exc:
            raise DownloadError('Expected response.numFound and response.docs in metadata') from exc
        if (not isinstance(docs, list) or len(docs) > PAGE_SIZE or count > options.max_records
                or (total is not None and count != total)):
            raise DownloadError('Metadata changed, exceeded limits or has an invalid page; narrow/retry search')
        total = count
        if (not docs and offset < total) or offset + len(docs) > total:
            raise DownloadError('Metadata pagination is incomplete or inconsistent')
        for doc in docs:
            if not isinstance(doc, dict) or not isinstance(doc.get('id'), str) or not doc['id']:
                raise DownloadError('Metadata record has no valid id')
            if doc['id'] in ids:
                raise DownloadError('Repeated record in metadata pagination; retry search')
            ids.add(doc['id'])
            records.append(doc)
        offset += len(docs)
    return records


def scalar(doc, field):
    value = doc.get(field)
    if isinstance(value, list):
        if len(value) != 1:
            raise DownloadError('Expected a single metadata ' + field)
        value = value[0]
    return value


def file_from_doc(doc):
    urls = doc.get('url')
    if not isinstance(urls, list):
        raise DownloadError('File metadata has no URL list')
    candidates = []
    for entry in urls:
        parts = entry.split('|') if isinstance(entry, str) else []
        if len(parts) == 3 and parts[2] == 'HTTPServer':
            # Do not silently upgrade HTTP: server support must be explicit.
            if parts[0].startswith('https://'):
                candidates.append(parts[0])
    if not candidates:
        raise DownloadError('File has no supported HTTPS HTTPServer URL')
    url = sorted(candidates)[0]
    parsed = https_url(url)
    name = unquote(parsed.path.rsplit('/', 1)[-1])
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,195}\.nc', name):
        raise DownloadError('Unsafe or unsupported NetCDF filename in metadata')
    size = integer(scalar(doc, 'size'), 'file size')
    algorithm = str(scalar(doc, 'checksum_type')).lower().replace('-', '')
    checksum = str(scalar(doc, 'checksum')).lower()
    length = {'sha256': 64, 'sha1': 40, 'md5': 32}.get(algorithm)
    if size == 0 or length is None or not re.fullmatch('[0-9a-f]{' + str(length) + '}', checksum):
        raise DownloadError('File requires positive size and a supported MD5/SHA1/SHA256 checksum')
    return File(name, url, size, algorithm, checksum)


def collect_files(filters, options):
    datasets = search(options.search_url, dict(filters, type='Dataset', latest='true', project='CMIP6'), options)
    files = {}
    expected_total = 0
    for dataset in datasets:
        expected = integer(scalar(dataset, 'number_of_files'), 'number_of_files')
        expected_total += expected
        if expected_total > options.max_records:
            raise DownloadError('Total file metadata exceeds --max-records; narrow filters')
        docs = search(options.search_url, {'type': 'File', 'dataset_id': dataset['id']}, options)
        if len(docs) != expected:
            raise DownloadError('Dataset file count differs from search results; retry search')
        for doc in docs:
            item = file_from_doc(doc)
            key = item.name.casefold()
            previous = files.get(key)
            if previous and (previous.name, previous.size, previous.checksum_type, previous.checksum) != (
                    item.name, item.size, item.checksum_type, item.checksum):
                raise DownloadError('Conflicting files share a filename; narrow filters')
            files.setdefault(key, item)
            if len(files) > options.max_records:
                raise DownloadError('Too many files; narrow filters or explicitly raise --max-records')
    return list(files.values())


def output_folder(root, filters):
    canonical = json.dumps(filters, sort_keys=True, separators=(',', ':'))
    digest = hashlib.sha256(canonical.encode()).hexdigest()[:16]
    variable = re.sub(r'[^A-Za-z0-9-]', '-', filters.get('variable_id', 'selection'))[:32]
    return Path(root).absolute() / (variable + '-' + digest)


def regular_path(path):
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise DownloadError('Expected a regular file, refusing: ' + path.name)
    if path.exists() and path.stat().st_nlink != 1:
        raise DownloadError('Refusing a hard-linked file: ' + path.name)


def complete(path, item, stop):
    regular_path(path)
    if not path.exists() or path.stat().st_size != item.size:
        return False
    digest = hashlib.new(item.checksum_type, usedforsecurity=False)
    with path.open('rb') as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            if stop.is_set():
                raise DownloadError('Interrupted')
            digest.update(chunk)
    return digest.hexdigest() == item.checksum


@contextmanager
def output_lock(folder):
    folder.mkdir(parents=True, exist_ok=True)
    if folder.is_symlink():
        raise DownloadError('Refusing a symlink output folder')
    path = folder / '.download.lock'
    regular_path(path)
    with path.open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise DownloadError('Another download is using this output folder') from exc
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def write_manifest(folder, filters, files):
    final = folder / 'manifest.json'
    temp = folder / 'manifest.json.tmp'
    regular_path(final)
    regular_path(temp)
    temp.write_text(json.dumps({'filters': filters, 'files': [asdict(item) for item in files]}, indent=2) + '\n')
    temp.replace(final)


def wget_attempt(command, timeout, stop):
    # No shell, personal wget config, credentials, HSTS writes or redirects.
    with subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) as process:
        deadline = time.monotonic() + timeout
        try:
            while process.poll() is None:
                if stop.wait(0.1) or time.monotonic() >= deadline:
                    raise DownloadError('Interrupted' if stop.is_set() else 'Transfer timed out')
            return process.returncode
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()


def download_file(item, folder, options, stop):
    final = folder / item.name
    partial = folder / (item.name + '.part')
    if complete(final, item, stop):
        return 'Verified existing ' + item.name
    if final.exists():
        raise DownloadError('Existing file failed verification; preserve/move it before retrying: ' + item.name)
    regular_path(partial)
    for attempt in range(options.attempts):
        if stop.is_set():
            raise DownloadError('Interrupted')
        if complete(partial, item, stop):
            partial.replace(final)
            return 'Verified ' + item.name
        if partial.exists() and partial.stat().st_size >= item.size:
            raise DownloadError('Partial file failed checksum/size; move it aside before retrying: ' + item.name)
        command = [options.wget, '--no-config', '--no-netrc', '--no-hsts', '--no-iri',
                   '--max-redirect=0', '--tries=1', '--timeout=60', '--continue',
                   '--output-document=' + str(partial), '--', item.url]
        try:
            code = wget_attempt(command, options.timeout, stop)
            if code == 0 and complete(partial, item, stop):
                partial.replace(final)
                return 'Verified ' + item.name
            reason = 'wget exit ' + str(code) + ' or incomplete/checksum mismatch'
        except DownloadError as exc:
            reason = str(exc)
        if stop.is_set() or attempt + 1 == options.attempts:
            break
        stop.wait(min(2 ** attempt, 4))
    raise DownloadError(item.name + ': ' + reason + '; partial retained, rerun the same filters')


def download_all(files, folder, options, stop):
    failures = 0
    iterator = iter(files)
    pool = ThreadPoolExecutor(max_workers=options.workers)
    pending = set()
    try:
        # Bound queued work as well as active wget processes.
        for _ in range(min(options.workers, len(files))):
            pending.add(pool.submit(download_file, next(iterator), folder, options, stop))
        while pending:
            done, pending = wait(pending, timeout=0.2, return_when=FIRST_COMPLETED)
            for future in done:
                try:
                    print(future.result(), flush=True)
                except (DownloadError, OSError) as exc:
                    failures += 1
                    print('Failed: ' + str(exc), file=sys.stderr, flush=True)
                item = next(iterator, None)
                if item is not None:
                    pending.add(pool.submit(download_file, item, folder, options, stop))
    finally:
        stop.set()
        for future in pending:
            future.cancel()
        pool.shutdown(wait=True, cancel_futures=True)
    return failures


def bounded(low, high):
    def parse(value):
        try:
            result = int(value)
        except ValueError as exc:
            raise argparse.ArgumentTypeError('Expected an integer') from exc
        if not low <= result <= high:
            raise argparse.ArgumentTypeError('Expected ' + str(low) + '..' + str(high))
        return result
    return parse


def get_params(argv=None):
    parser = argparse.ArgumentParser(description='CMIP6 search and verified downloads (' + VERSION + ')')
    for facet in FACETS:
        parser.add_argument('--' + facet, help='ESGF ' + facet + ' filter')
    parser.add_argument('--version', action='version', version=VERSION)
    parser.add_argument('--output', type=Path, default=Path('data'), help='Output root (default: data)')
    parser.add_argument('--search-url', default=SEARCH_URL, help='HTTPS ESGF Solr search endpoint')
    parser.add_argument('--workers', type=bounded(1, 8), default=2)
    parser.add_argument('--attempts', type=bounded(1, 5), default=3, help='Total attempts per request/file, independent of workers')
    parser.add_argument('--timeout', type=bounded(1, 3600), default=300, help='Metadata socket / whole transfer attempt timeout in seconds')
    parser.add_argument('--max-records', type=bounded(1, 100000), default=10000, help='Cap each search and total file records including replicas')
    parser.add_argument('--dry-run', action='store_true', help='Search metadata and print plan; no files written or downloaded (requires network)')
    options = parser.parse_args(argv)
    filters = {key: getattr(options, key).strip() for key in FACETS if getattr(options, key) and getattr(options, key).strip()}
    if not (sys.argv[1:] if argv is None else argv):
        for key in ('variable_id', 'frequency', 'experiment_id', 'source_id'):
            value = input('Enter ' + key + ' (blank to omit): ').strip()
            if value:
                filters[key] = value
    if not filters:
        parser.error('Provide at least one search filter; use --help')
    if any(len(value) > 512 or any(ord(c) < 32 or ord(c) == 127 for c in value) for value in filters.values()):
        parser.error('Filters must be at most 512 characters with no control characters')
    https_url(options.search_url)
    if urlsplit(options.search_url).query:
        parser.error('--search-url must not include query parameters')
    return options, filters


def main(argv=None):
    try:
        options, filters = get_params(argv)
        if not options.dry_run:
            options.wget = shutil.which('wget')
            if not options.wget:
                raise DownloadError('GNU wget is required for downloads; install it or use --dry-run')
        print('Searching metadata (no data transfers until the complete plan validates)', flush=True)
        files = collect_files(filters, options)
        if not files:
            print('No matching files; no output written')
            return 0
        folder = output_folder(options.output, filters)
        print(str(len(files)) + ' unique files, ' + str(sum(item.size for item in files)) + ' bytes; output: ' + str(folder), flush=True)
        if options.dry_run:
            print('Dry run: no output written and no files downloaded')
            return 0
        with output_lock(folder):
            write_manifest(folder, filters, files)
            failures = download_all(files, folder, options, threading.Event())
        print('Finished: ' + str(len(files) - failures) + ' verified, ' + str(failures) + ' failed')
        return 1 if failures else 0
    except (DownloadError, OSError, ValueError) as exc:
        print('Error: ' + str(exc), file=sys.stderr)
        return 1
    except (KeyboardInterrupt, EOFError):
        print('Interrupted; partial files retained. Rerun the same filters to resume.', file=sys.stderr)
        return 130


if __name__ == '__main__':
    sys.exit(main())
