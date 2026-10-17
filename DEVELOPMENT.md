# Development

Use maintained Python 3.11+ on Linux/macOS. The program uses the standard library;
no Python dependency installation, package manager or build step is needed.

## Checks

From the repository root:

```sh
python3 -B tools/check.py
```

This is the shared local/CI/hook gate. It compiles active sources, imports under
side-effect guards, denies socket connections and runs only `test_downloader.py`
from a disposable cwd, with warnings treated as errors and a 60-second deadline.
Tests fake subprocess/network boundaries and create tiny synthetic files. Preserve
those guards. Never use broad test discovery: `test/` contains historical manual
experiments that prompt, write logs or contact external services.

For real wget, TLS, range-resume and cancellation behavior, install GNU wget with
HTTPS support and openssl, then run:

```sh
python3 -B -W error tools/check_transfer.py
```

This optional check binds only loopback and generates temporary certificates and
tiny synthetic content. It starts wget, verifies range and no-range behavior,
TLS trust/rejection, checksum failure, redirects, timeout and cancellation. The
fixture explicitly trusts its own certificate through a temporary wrapper; it
never disables certificate verification or changes system trust. Its temp directory
must permit execution. Prefer a disposable environment with external networking
disabled. Ordinary CI and quick hooks use the mocked gate and need neither wget
nor openssl. These checks do not contact an ESGF endpoint.

An optional hook is supplied at `.githooks/pre-commit`; it runs the same quick gate.
Inspect existing local hook configuration before opting in using
`git config --local core.hooksPath .githooks`. Restore the prior configuration to
undo it. No installer activates hooks and checks never stage or alter files.

## Source map and review invariants

- `get_params`, `output_folder`: retain facet flags; validate resource settings and
  keep filter text out of filesystem structure and shell interpretation.
- `fetch_json`, `search`, `collect_files`: bounded retries/pages, complete planning,
  strict metadata/filename/checksum validation, deterministic duplicate handling.
- `output_lock`, `regular_path`, `write_manifest`: one writer per selection, atomic
  manifest replacement; output is trusted local storage, not a shared service.
- `complete`, `download_file`, `wget_attempt`, `download_all`: size and checksum
  before promotion/skip, bounded jobs and subprocess lifetimes, retained partials.

A good bug report gives Python/wget/OS versions, a minimal synthetic reproduction,
expected behavior and redacted error/metadata. Do not attach research data,
credentials, personal paths or signed URLs. For a change, explain the observed
problem, smallest fix, relevant regression, executed checks and remaining limits.
Live service checks require a separately scoped decision; tests stay offline.

## Versions, dependencies and attribution

The single version constant, CLI output and change notes identify version 5.0.0.
Tags 1.x–4.0.0 and existing history remain historical records. Keep release tags
on their original commits. Before delivering a version, review the full diff, run
both local checks, verify a bounded live workflow, and review output/recovery
compatibility, the dependency exception and MIT attribution. Align the version
and change notes before delivery; confirm hosted CI on the uploaded commit before
manually tagging that exact commit. Local files do not establish that a tag or
GitHub Release has been published. Nothing here creates tags or pushes. There is no release bot or runtime
package to distribute.

There are no pip dependencies to audit. Python, GNU wget, TLS libraries and CA
certificates are supplied by the OS/runtime; maintain and audit them through that
provider. A passing check is not a vulnerability audit. GitHub Actions are pinned
to reviewed upstream commits; revisit pins during maintenance, without a dependency
bot for an otherwise dependency-free script. Hosted CI results remain separate
from local checks.

### Dependency exception — checked 2026-10-16

The test environment uses Debian trixie GNU wget **1.25.0-2**. Its
[security tracker](https://security-tracker.debian.org/tracker/source-package/wget)
still lists unresolved advisories. This is not a zero-vulnerability result, nor
an audit of every OS/TLS dependency:

| Advisory | Scope in this client / revisit trigger |
| --- | --- |
| [CVE-2026-58470](https://security-tracker.debian.org/tracker/CVE-2026-58470) | Content-Range integer overflow is relevant to resume. Checksums prevent accepting incorrect bytes but do not fix the parser. Use trusted data nodes; revisit when the OS supplies the upstream fix. |
| [CVE-2026-58471](https://security-tracker.debian.org/tracker/CVE-2026-58471) | Filename charset conversion. ASCII validated names, explicit output paths and disabled IRI narrow exposure; this is not proof of non-exploitability. Revisit with the patched package. |
| CVE-2026-58472 / CVE-2026-58469 | HTML conversion / Metalink paths are not enabled by this client. Reassess if adding either feature or changing wget builds. |
| CVE-2026-15146 / CVE-2026-16599 | FTP passive requests / FTP OPIE. HTTPS-only inputs and disabled redirects exclude the intended FTP path. Reassess if protocol policy changes. |
| CVE-2021-31879 | Authorization forwarding on redirects. Credentials, netrc and file redirects are disabled. Reassess before supporting authenticated downloads. |

No exploits or hostile payloads are run by the checks. Do not compile a private
wget fork or change transfer engines merely to hide an audit finding. Prefer a
maintained patched OS package and rerun both gates after the update. Until then,
resume against an untrusted server is outside the verified use of this utility.

Retain existing source/contact/DOI attribution and all third-party notices. The
project is [MIT licensed](LICENSE); preserve that copyright and permission notice
in source copies and substantial portions. The DOI badge is a citation link. Do not bundle external tools or invent
attribution or research results. Original exploratory scripts remain unchanged.
