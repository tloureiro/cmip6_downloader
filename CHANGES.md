# Changes

## 5.0.0

- Add the MIT project license; retain historical contact, citation and attribution.
- Update the default search endpoint to the current Metagrid host; retain the
  configurable HTTPS endpoint and all facet flags.

- Remove import-time manager processes and log truncation. Replace shell commands
  and disabled TLS verification with bounded, argument-based GNU wget transfers.
- Validate complete paginated metadata, sizes, checksums and safe filenames before
  transfers. Collapse matching replicas; reject conflicting destinations.
- Separate worker/attempt limits; propagate failed transfers to a nonzero exit.
  Bound pending jobs, child lifetimes and retries; terminate children on Ctrl-C.
- Retain `.part` files, verify before atomic rename/skip and lock each selection
  against concurrent runs. Preserve invalid finals/partials for explicit recovery.
- Add deterministic hashed output folders and `manifest.json`. Existing 4.0.0
  folders/list files are untouched, not automatically migrated. Require maintained
  Python 3.11+ on POSIX and HTTPS `.nc` records with supported size/checksum metadata.
- Add offline regressions, optional tiny HTTPS/wget checks, setup/recovery/source
  guidance and an opt-in hook/shared CI gate. A bounded live one-file check
  verifies metadata selection, HTTPS interruption/resume, SHA256 and verified skip.
  Wider service/platform support remains unverified; HTTP-only records still fail
  the complete plan before transfer. The documented wget exception remains.

## Historical releases

Existing Git tags 1.0.0, 1.1.0, 1.2.0, 2.0.0, 3.0.0.alpha, 3.0.0 and 4.0.0 remain
the release record. The prior README described version 2 while source/tag were
4.0.0. Historical release notes are not reconstructed here; existing tags remain
on their original commits.
