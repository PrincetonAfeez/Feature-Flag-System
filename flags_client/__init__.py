"""Python client SDK package — deferred to V1.

The MVP proves the architecture with the evaluation core, the Django service
layer, the admin CLI, and the read-only snapshot API. The client SDK (local
snapshot evaluation, polling refresh, and SSE refresh with polling fallback) is
explicitly V1 scope — see the README "Deferred to V1" section and
docs/adr/0001-local-snapshot-local-evaluation.md / 0002.

This module is an intentional V1 placeholder in the source tree. It is **not**
installed as a package in 0.1.x (see `pyproject.toml`); use
`examples/minimal_consumer/` for the local-evaluation demo.
"""
