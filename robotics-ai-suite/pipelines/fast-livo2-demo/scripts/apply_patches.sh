#!/usr/bin/env bash
# Apply the Intel patches on top of the pristine FAST-LIVO2 submodule
# checkout. Safe to re-run: skips patches already applied unchanged, and
# reapplies (after resetting off the stale commit) any patch edited since.
#
# Usage: ./apply_patches.sh
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/env.sh"

PATCH_DIR="${DEMO_DIR}/patches"

cd "${FASTLIVO2_SRC}"

if [[ ! -e .git ]]; then
  echo "FAST-LIVO2 submodule is not initialized. Run:" >&2
  echo "  git submodule update --init ${FASTLIVO2_SRC}" >&2
  exit 1
fi

if [[ -n "$(git status --porcelain)" ]]; then
  echo "FAST-LIVO2 checkout has local changes; refusing to apply patches on top of a dirty tree." >&2
  echo "Reset it to the pristine commit recorded by the superproject first." >&2
  exit 1
fi

# Applied per-patch (checked against each patch's own Subject: header, not a
# single "last patch" marker) so this stays safe to re-run after a checkout
# that already has some - but not all - patches applied, e.g. a tree built
# before a new NNNN-*.patch was added here.
#
# Each applied commit is tagged with a trailer carrying a hash of the .patch
# file it came from, so a re-run can tell "already applied, unchanged" (skip)
# apart from "already applied, but the .patch file was edited since" (that
# commit and everything after it get reset off and reapplied fresh).
# Commits from before this tagging existed have no trailer; treat those as
# an unverifiable baseline and leave them alone rather than resetting.
find_commit_for_subject() {
  # No early `exit` on match: awk closing the pipe before `git log` finishes
  # writing the (potentially long) upstream history would SIGPIPE it, which
  # aborts the script under `set -o pipefail`.
  git log --format='%H%x09%s' | awk -F'\t' -v s="$1" '$2==s && !found{print $1; found=1}'
}

trailer_hash_for_commit() {
  git log -1 --format=%B "$1" | { grep -m1 '^X-Patch-Sha256: ' || true; } | awk '{print $2}'
}

echo "==> Applying Intel patches from ${PATCH_DIR}"
applied_any=0
for patch in "${PATCH_DIR}"/0*.patch; do
  subject="$(grep -m1 '^Subject: ' "${patch}" | sed -E 's/^Subject: (\[PATCH[^]]*\] )?//')"
  patch_hash="$(sha256sum "${patch}" | awk '{print $1}')"

  existing_commit="$(find_commit_for_subject "${subject}")"
  if [[ -n "${existing_commit}" ]]; then
    existing_hash="$(trailer_hash_for_commit "${existing_commit}")"
    if [[ -z "${existing_hash}" ]]; then
      echo "==> Already applied: ${subject}, skipping (pre-existing commit, no hash on record)"
      continue
    elif [[ "${existing_hash}" == "${patch_hash}" ]]; then
      echo "==> Already applied: ${subject}, skipping"
      continue
    else
      echo "WARNING: ${subject}: .patch file changed since commit ${existing_commit:0:7} was applied." >&2
      echo "WARNING: discarding ${existing_commit:0:7} and every commit after it (any manual fixes made" >&2
      echo "WARNING: directly on top of it, rather than via this .patch file, will be lost) and reapplying" >&2
      echo "WARNING: from the updated .patch file. Recoverable via 'git reflog' if this is not intended." >&2
      git reset --hard "${existing_commit}^"
    fi
  fi

  git am --keep-cr "${patch}"
  git commit --amend -q -m "$(git log -1 --format=%B)
X-Patch-Sha256: ${patch_hash}"
  applied_any=1
done

if [[ "${applied_any}" -eq 0 ]]; then
  echo "==> All patches already applied (HEAD: $(git log -1 --format='%h %s'))"
else
  echo "==> Patches applied. HEAD: $(git log -1 --format='%h %s')"
fi
