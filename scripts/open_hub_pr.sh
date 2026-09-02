#!/usr/bin/env bash
# Open the weekly FluSight submission PR: branch on the fork, PR against
# cdcepi:main. One forecast file per PR (hub convention); the model metadata is
# bundled ONLY when upstream does not carry it yet (hub precedent #2329).
#
# Required env:
#   SUBMISSION_FILE  <ref>-JGracey-prime_radiant.csv produced by the dry run
#   METADATA_FILE    rendered JGracey-prime_radiant.yml (same artifact)
#   FORK_PUSH_URL    push URL for the fork (carries the PAT in CI; never echoed)
# Optional env (defaulted; overridden by the fixture tests):
#   UPSTREAM_URL     hub clone URL       [https://github.com/cdcepi/FluSight-forecast-hub]
#   UPSTREAM_REPO    owner/name for gh   [cdcepi/FluSight-forecast-hub]
#   FORK_HEAD_OWNER  fork owner for --head [JeremyGracey-AI]
#   WORK_DIR         scratch dir         [mktemp -d]
#   DRY_RUN          "1" = print the push/pr commands instead of executing them
set -euo pipefail

: "${SUBMISSION_FILE:?}" "${METADATA_FILE:?}" "${FORK_PUSH_URL:?}"
UPSTREAM_URL="${UPSTREAM_URL:-https://github.com/cdcepi/FluSight-forecast-hub}"
UPSTREAM_REPO="${UPSTREAM_REPO:-cdcepi/FluSight-forecast-hub}"
FORK_HEAD_OWNER="${FORK_HEAD_OWNER:-JeremyGracey-AI}"
WORK_DIR="${WORK_DIR:-$(mktemp -d)}"
DRY_RUN="${DRY_RUN:-0}"

MODEL_ID="JGracey-prime_radiant"
file_name=$(basename "$SUBMISSION_FILE")
ref="${file_name:0:10}"
if ! [[ "$ref" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]] || [ "$file_name" != "${ref}-${MODEL_ID}.csv" ]; then
    echo "unexpected submission filename: ${file_name}" >&2
    exit 64
fi

# Structural freshness gate (adversarial finding): off-season, `auto` resolves
# to the LAST enumerated round — months stale — and it validates green. The
# hub window is Sun..Wed before the Saturday reference date (3-6 days out;
# a UTC-Thursday dispatch inside ET Wednesday is 2), so [0, 13] is generous
# yet kills every stale round. fromisoformat also rejects impossible dates
# (2026-13-40) that pass the format regex.
days_until=$(python3 -c "import datetime as d, sys
try: ref = d.date.fromisoformat(sys.argv[1])
except ValueError: sys.exit(64)
print((ref - d.date.today()).days)" "$ref") || {
    echo "unexpected submission filename: ${file_name}" >&2
    exit 64
}
if [ "$days_until" -lt 0 ] || [ "$days_until" -gt 13 ]; then
    echo "refusing stale or far-future submission: ${ref} is ${days_until} day(s) from today" >&2
    exit 65
fi
branch="submit-${ref}"

submission_abs="$(cd "$(dirname "$SUBMISSION_FILE")" && pwd)/$(basename "$SUBMISSION_FILE")"
metadata_abs="$(cd "$(dirname "$METADATA_FILE")" && pwd)/$(basename "$METADATA_FILE")"

rm -rf "$WORK_DIR/hub"  # a reused WORK_DIR must not kill the clone (retry path)
git clone --depth 1 "$UPSTREAM_URL" "$WORK_DIR/hub"
cd "$WORK_DIR/hub"
git checkout -b "$branch"

mkdir -p "model-output/${MODEL_ID}"
cp "$submission_abs" "model-output/${MODEL_ID}/"
git add "model-output/${MODEL_ID}/${file_name}"

if [ ! -f "model-metadata/${MODEL_ID}.yml" ]; then
    echo "bundling model metadata (not yet in upstream)"
    mkdir -p model-metadata
    cp "$metadata_abs" "model-metadata/${MODEL_ID}.yml"
    git add "model-metadata/${MODEL_ID}.yml"
fi

git -c user.name="Jeremy Gracey" -c user.email="jeremy.a.gracey@gmail.com" \
    commit -m "Add ${MODEL_ID} forecast for ${ref}"

if [ "$DRY_RUN" = "1" ]; then
    echo "DRY RUN — would push HEAD:${branch} to the fork"
    echo "DRY RUN — would run: gh pr create --repo ${UPSTREAM_REPO} --base main --head ${FORK_HEAD_OWNER}:${branch}"
    exit 0
fi

# --force is safe and makes retries idempotent: the branch lives on OUR fork,
# is per-week disposable, and a stranded tip from a partial failure must never
# block the resubmission (adversarial finding: non-FF rejection dead-ended
# every same-week retry until the branch was hand-deleted).
git push --force "$FORK_PUSH_URL" "HEAD:${branch}"
open_prs=$(gh pr list --repo "$UPSTREAM_REPO" --head "${FORK_HEAD_OWNER}:${branch}" \
    --state open --json number --jq length)
if [ "$open_prs" -gt 0 ]; then
    echo "hub PR for ${branch} already open — branch updated, nothing to create"
    exit 0
fi
gh pr create \
    --repo "$UPSTREAM_REPO" \
    --base main \
    --head "${FORK_HEAD_OWNER}:${branch}" \
    --title "${MODEL_ID} ${ref}" \
    --body "Weekly quantile forecast from https://github.com/JeremyGracey-AI/prime-radiant, validated against hub-config/tasks.json before submission."
echo "opened hub PR for ${ref}"
