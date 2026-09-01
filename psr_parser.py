"""Commit parser for python-semantic-release tolerating `[actor] type(scope):`.

The house convention prefixes agent-authored commits with `[claude] ` before a
conventional-commits subject. psr's stock ConventionalCommitParser anchors its
regex at string start, so every prefixed commit fails to parse (verified
empirically against psr 10.6.2). This subclass strips exactly one leading
`[word] ` token, then defers to the stock parser.

Loaded by psr via the FILE-PATH form in pyproject
(`commit_parser = "psr_parser.py:ActorPrefixConventionalParser"`) — the bare
module form fails because the repo root is not on sys.path when psr imports.
psr itself never lives in the project env (its tomlkit floor conflicts with
gradio's cap), so the semantic_release import below only resolves under
`uvx python-semantic-release==10.6.2` or the release workflow's action; the
pure strip logic stays importable (and unit-tested) without it.
"""

import re

_ACTOR_PREFIX = re.compile(r"^\[[\w.-]+\]\s+")


def strip_actor_prefix(message: str) -> str:
    """Remove one leading `[actor] ` token from a commit message, if present."""
    return _ACTOR_PREFIX.sub("", message, count=1)


try:
    # psr is never in the project env (tomlkit conflict with gradio) — resolved
    # only under uvx / the release workflow, hence the scoped pyright ignore.
    from semantic_release.commit_parser.conventional import (  # pyright: ignore[reportMissingImports]
        ConventionalCommitParser,
    )
except ImportError:  # pragma: no cover — project env; psr runs isolated
    ConventionalCommitParser = None  # type: ignore[assignment, misc]
else:

    class ActorPrefixConventionalParser(ConventionalCommitParser):
        def parse_message(self, message: str):  # noqa: ANN201 — psr's own signature
            return super().parse_message(strip_actor_prefix(message))
