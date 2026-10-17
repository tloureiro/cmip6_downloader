# CMIP6 downloader

A Python CLI for selecting CMIP6 climate-model files through ESGF search metadata
and downloading them into a local research folder. Filter by variable, experiment,
model, frequency and other facets, inspect the planned size, then rerun the same
selection to verify existing files and resume partial transfers.

This is a small research utility, not a scientific analysis pipeline. It does not
interpret NetCDF contents or establish scientific validity. Version **5.0.0**
introduces verified completion, explicit recovery and bounded transfers; see
[CHANGES.md](CHANGES.md) and the migration notes below.

A bounded **live check on 2026-10-16** selected one 52.4 MB CanESM5 file through
the current search service, interrupted its HTTPS transfer, resumed with HTTP
206, verified its SHA256 and skipped the verified file on rerun. This establishes
one public, credential-free node/selection; wider service/platform compatibility
remains unverified. Other replicas in that selection advertised HTTP-only URLs:
a selection containing those records is rejected before any transfer.

## First check: entirely offline

Requires a maintained **Python 3.11+** on Linux or macOS. There are **no third-party
Python packages**, environment files, accounts or pip installation steps.

```sh
python3 --version
python3 -B tools/check.py
python3 -B cmip6_downloader.py --help
python3 -B cmip6_downloader.py --version
```

The check uses mocked metadata, tiny synthetic files and a temporary working
directory. It blocks socket connections, checks imports for side effects and never
runs the old exploratory scripts in `test/`. It needs neither wget nor real data.
See [DEVELOPMENT.md](DEVELOPMENT.md) for the optional real-wget loopback check.

## Select and download

Downloads additionally require **GNU wget 1.21+ with HTTPS support** and working
system CA certificates. Install Python/wget with your OS package manager or Python
from [python.org](https://www.python.org/downloads/). Verify `wget --version` says
GNU Wget and includes `+https`. Native Windows is unsupported (POSIX file locks).
The checked Debian wget package has unresolved advisories, including a resume
header parser issue; see the dated [dependency exception](DEVELOPMENT.md#dependency-exception--checked-2026-10-16).

The following commands **contact ESGF**. The first queries metadata only and
prints the total unique file count, expected bytes and output folder; it writes
nothing. Review that plan and available disk space before running the second.

```sh
python3 cmip6_downloader.py --variable_id tas --frequency mon \
  --experiment_id historical --source_id CanESM5 --variant_label r1i1p1f1 \
  --table_id Amon --grid_label gn --data_node eagle.alcf.anl.gov \
  --max-records 1 --dry-run

python3 cmip6_downloader.py --variable_id tas --frequency mon \
  --experiment_id historical --source_id CanESM5 --variant_label r1i1p1f1 \
  --table_id Amon --grid_label gn --data_node eagle.alcf.anl.gov \
  --max-records 1 --output ./data
```

With no arguments, four prompts ask for variable, frequency, experiment and source.
Blank fields are omitted; at least one filter is required. `--help` lists all
retained facet flags. Comma-separated filter values are passed to ESGF unchanged.
`--search-url` selects an HTTPS Solr search endpoint without query parameters; the
default is `https://metagrid.esgf-west.org/proxy/search`; the historical
`aims2.llnl.gov` host redirects there. Availability, API changes,
access restrictions and data-node policies vary. This tool supports public,
credential-free HTTPS file URLs; it does not sign in or accept credentials.

## Output and recovery

```text
data/<variable>-<selection-hash>/
  manifest.json       # validated selection, URLs, sizes and checksums
  .download.lock      # persistent file; OS lock releases automatically on exit
  example.nc.part     # unfinished transfer, retained for the next run
  example.nc          # promoted only after size + checksum verification
```

The hash comes from sorted filters, so argument order does not change the folder.
Use the same filters and output root to resume. Metadata is searched again on each
run; the manifest records the most recent validated plan, not a permanent archive.
Files unrelated to the plan are neither counted as complete nor removed. Existing
files are rehashed before skipping. A failed run exits **1**, invalid arguments
**2**, interruption **130**, and a completed or empty search **0**. Errors go to
stderr, progress to stdout. There is no import-time log or overwritten `logs.txt`.

- **Connection failure or timeout:** rerun the same selection. Short `.part` files
  resume through wget's range requests; a server ignoring ranges may restart them.
- **Checksum mismatch, oversized partial, or invalid existing final:** the file is
  preserved. Inspect it and move it out of the output folder before retrying. A
  checksum mismatch cannot be repaired by blindly appending more bytes.
- **TLS failure (wget code 5):** check your CA installation and endpoint. Certificate
  checks cannot be disabled through this CLI or personal wget configuration.
- **HTTP error (wget code 8), redirect, or unsupported URL:** inspect the data-node
  service and choose suitable filters/endpoint. All file redirects are rejected,
  including HTTPS redirects, to prevent downgrade and unexpected destinations.
- **Missing/malformed metadata, changing pagination or filename conflict:** the
  complete plan must validate before any transfer. Retry/narrow the search rather
  than treating an incomplete list as success.
- **Another run is active:** wait for it or stop it normally. Do not remove the lock
  file while a run is active. Ctrl-C stops queued work and terminates active wget
  children; verified files and partials remain. Metadata cancellation can wait for
  the socket timeout.

**Migration from 4.0.0:** output folders now use a hash instead of concatenated
filter values. Old folders and `*_files_url_list.txt` files remain untouched and
are not automatically trusted/reused. After making a backup, you can copy selected
old `.nc` files into the new printed folder; they will be verified on the next run.
Never treat the old file-count success message as an integrity check.

## Operational limits and decisions

- Defaults: **2 workers**, **3 total attempts** per request/file, **300 seconds**
  metadata socket timeout or whole transfer-attempt deadline. `--workers` accepts
  1–8, `--attempts` 1–5 and `--timeout` 1–3600. Wget also has a 60-second idle
  timeout and one internal try. Backoff is at most 4 seconds. Increase the deadline
  deliberately for large/slow files; raising workers does not raise attempts.
- Metadata is fetched sequentially, 500 records/page, at most 4 MiB/response.
  `--max-records` defaults to 10,000 (maximum 100,000), bounding each search and
  total file records, including replicas. Narrow filters to reduce resource use.
  Queued transfers are bounded to the worker count. There is no disk quota or
  aggregate run deadline; the printed byte count is a plan, not a reservation.
- Only safe `.nc` basenames are accepted. Conflicting names (including case-only
  conflicts) fail; replicas with matching name, size and checksum collapse to one
  destination. One HTTPS URL is chosen per file; automatic mirror failover is
  deferred. Unsupported/missing checksums or HTTP-only records fail the plan.
- MD5, SHA1 and SHA256 metadata checksums are supported. Legacy hashes detect
  accidental corruption; they do not authenticate a hostile source. Trust the
  search endpoint/data nodes. URLs are saved in the manifest and passed to wget;
  do not supply signed/private URLs. TLS does not make metadata trustworthy.
- Output roots must be under your control. Symlinks/nonregular/hard-linked file
  destinations are refused; this is not a defense against another local user
  modifying the directory concurrently. System proxies/CA settings still apply;
  personal wget config, netrc, redirects and HSTS persistence are disabled.
- Offline checks verify the client contract and local transfer mechanics. They do
  not prove current ESGF schemas, service availability, research results, storage
  durability after power loss, Windows support or high-volume performance.

## Source and maintenance

[cmip6_downloader.py](cmip6_downloader.py) contains argument handling, metadata
pagination/validation, planning, locking and transfers. [test_downloader.py](test_downloader.py)
protects those boundaries; [DEVELOPMENT.md](DEVELOPMENT.md) explains checks,
contributions and release decisions. A screenshot adds little to this CLI: the
copyable commands, output layout and recovery messages carry the useful detail.

The original Git history, release tags, contact and Zenodo DOI are retained.
The project is licensed under [MIT](LICENSE). Retain its copyright and license
notice when reusing the source. GNU wget is invoked as an external tool and is not
bundled here; its own license is separate.

Bugs, questions or requests: thiago@tloureiro.com

[![DOI](https://zenodo.org/badge/183989782.svg)](https://zenodo.org/badge/latestdoi/183989782)
