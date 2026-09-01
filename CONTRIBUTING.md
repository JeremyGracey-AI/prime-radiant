# Contributing

This is a personal research project; issues and PRs are welcome, with the
caveat that the bar below is enforced by CI and by review.

## Environment

```sh
uv sync --all-groups     # or: make install-dev
pre-commit install
```

Python ≥3.11 (3.11–3.13 tested in CI), `uv` for everything — there is
deliberately no `requirements*.txt` in this repo (a test asserts it), and
macOS needs Homebrew `libomp` for LightGBM.

## Gates

```sh
make check            # ruff + format + pyright + offline pytest, coverage = 100
make test-integration # network: real hub clone, S3 benchmarks, byte-regen tests
```

Run the gate commands directly — never piped through `head`/`tail` (a piped
gate once swallowed a failing exit code; it is now a house rule). Committed
artifacts (`reports/`, `serve_data/`, `tests/golden/`) must byte-regenerate via
their integration tests; do not hand-edit them.

## Process

- **TDD**: production code follows a failing test. Bug fixes start with a
  regression test that reproduces the bug.
- **Vintage discipline is non-negotiable**: never train, score, or anchor on
  data dated after the forecast origin. These are tested invariants.
- Every dependency version cap carries a why-comment; GitHub Actions are
  SHA-pinned with a `# vX.Y.Z` comment.
- Substantial changes get adversarial review before merge (see `AI-USE.md` for
  how agent-assisted verification works here).

## Commits

Conventional Commits, with an actor prefix for agent-authored work:

```
[claude] type(scope): subject     # agent-authored
type(scope): subject              # human-authored
```

Both forms parse for release automation (`psr_parser.py` strips the actor
prefix). Releases are cut deliberately via the manually-dispatched `release`
workflow, never automatically.
