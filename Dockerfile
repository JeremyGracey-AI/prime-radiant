# Multi-stage uv build (astral's documented shape), digest-pinned. Ships the
# CLI and its locked venv ONLY — no repo data: forecast subcommands resolve
# hub/tasks/data paths from the working directory, so mount them at /app
# (e.g. `docker run -v $PWD/data:/app/data prime-radiant epi validate ...`).
# Digests resolved 2026-08-31; Dependabot's docker ecosystem keeps them fresh.

FROM python:3.12-slim@sha256:e5c9fa26ffb76e11e0f054f30dc2523a2f9693f0c36c0cf1e39b27e152d899fc AS builder
COPY --from=ghcr.io/astral-sh/uv@sha256:d1cbaeadc234fe19c0d93daabcf5e98738cd93c6d1dd4918ef6aa30735feb23a /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0

WORKDIR /app

# deps layer first (cached until the lockfile changes), project second
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-dev --no-install-project
COPY pyproject.toml uv.lock README.md ./
COPY src/ src/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

FROM python:3.12-slim@sha256:e5c9fa26ffb76e11e0f054f30dc2523a2f9693f0c36c0cf1e39b27e152d899fc

# libgomp1 is REQUIRED: lightgbm 4.7.0's manylinux wheel lists libgomp.so.1 in
# its ELF DT_NEEDED and does NOT bundle it; slim images lack it (verified by
# wheel inspection 2026-08-31). libstdc++6/libgcc-s1 are already in the base.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --uid 999 --create-home nonroot
COPY --from=builder --chown=nonroot:nonroot /app /app

USER nonroot
WORKDIR /app
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

ENTRYPOINT ["prime-radiant"]
