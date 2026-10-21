#!/usr/bin/env bash
# Builds upstream TensorFold with the opt-in patches in engine/patches: the native server and drama3-generate.
#
# Usage: scripts/build-engine.sh [BUILD_DIR]        (default: build/tensorfold in this repo)
#
# Environment:
#   ZIG          Zig 0.17.0 executable (default: zig on PATH)
#   NVCC         CUDA 13 nvcc (default: nvcc on PATH)
#   JOBS         parallel build jobs (default: Zig's choice)
#
# Every run checks out the pinned upstream commit and re-applies the whole series, so the result does not depend
# on what an earlier run left behind. Output: BUILD_DIR/zig-out/native/bin/tensorfold-native and
# BUILD_DIR/zig-out/bin/drama3-generate.
set -euo pipefail

repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
build=${1:-$repo/build/tensorfold}
zig=${ZIG:-zig}
nvcc=${NVCC:-nvcc}

die() {
  echo "build-engine: $*" >&2
  exit 1
}

# shellcheck source=../engine/UPSTREAM
. "$repo/engine/UPSTREAM"
[[ -n ${TENSORFOLD_REPOSITORY:-} && -n ${TENSORFOLD_COMMIT:-} ]] || die "engine/UPSTREAM must set TENSORFOLD_REPOSITORY and TENSORFOLD_COMMIT"

shopt -s nullglob
patches=("$repo"/engine/patches/*.patch)
((${#patches[@]})) || die "engine/patches has no *.patch files"

command -v git >/dev/null || die "git not found"
zig=$(command -v "$zig") || die "Zig not found; set ZIG"
nvcc=$(command -v "$nvcc") || die "nvcc not found; set NVCC"

if [[ -e $build ]]; then
  git -C "$build" rev-parse --git-dir >/dev/null 2>&1 || die "$build exists and is not a git checkout"
  [[ -z $(git -C "$build" status --porcelain --untracked-files=no) ]] || die "$build has local changes; refusing to discard them"
  git -C "$build" am --abort >/dev/null 2>&1 || true
else
  git clone --quiet --no-checkout "$TENSORFOLD_REPOSITORY" "$build"
fi
git -C "$build" cat-file -e "$TENSORFOLD_COMMIT^{commit}" 2>/dev/null || git -C "$build" fetch --quiet origin "$TENSORFOLD_COMMIT"
git -C "$build" checkout --quiet --detach "$TENSORFOLD_COMMIT"

# A fixed committer and dates taken from the patches make the patched HEAD the same on every run.
GIT_COMMITTER_NAME=build-engine GIT_COMMITTER_EMAIL=build-engine@example.invalid \
  git -C "$build" am --quiet --committer-date-is-author-date "${patches[@]}" \
  || { git -C "$build" am --abort || true; die "the patch series does not apply to $TENSORFOLD_COMMIT"; }

want=$(<"$build/.zig-version")
have=$("$zig" version)
[[ $have == "$want" ]] || die "Zig $have found; the engine pins $want"

cd "$build"
"$zig" build native drama3-generate -Dnvcc="$nvcc" --summary all ${JOBS:+-j"$JOBS"}

echo "engine: $TENSORFOLD_COMMIT + ${#patches[@]} patches = $(git rev-parse HEAD)"
sha256sum zig-out/native/bin/tensorfold-native zig-out/bin/drama3-generate
