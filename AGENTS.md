# Working in this repository

Read README.md and DEVELOPMENT.md, then inspect the affected source and tests
before importing or running them. Preserve existing edits, Git history, tags,
attribution and user files. Keep the single-script workflow unless a concrete
behavior fix requires otherwise.

- Run `python3 -B tools/check.py` with maintained Python 3.11+. It is the shared
  offline gate. Never execute or discover the historical `test/` experiments.
- Use mocked metadata and tiny synthetic fixtures only. Do not start live ESGF
  searches, climate downloads, personal configurations or research jobs as checks.
  The optional `tools/check_transfer.py` uses loopback only and needs wget/openssl.
- Keep imports free of file/network/process effects. Never build shell commands
  from filters, metadata or paths; TLS verification must remain enabled.
- Preserve bounded resources, complete metadata planning, collision rejection,
  size/checksum verification, lock ownership and recoverable `.part` files.
- Account for output-layout compatibility, errors/exits and interruption. Add
  meaningful regressions for material behavior fixes, not implementation mirrors.
- Record actual commands/results and remaining limits. Do not infer live service
  compatibility, scientific correctness, a license or ownership from tests.
- Do not change accounts, publish, push, rewrite history or run real research jobs.
