#!/usr/bin/env bash
# Builds the TensorFold engine for the chosen Drama 3 weights.
#
# Usage: scripts/build-engine.sh [--weights full|nvfp4] [BUILD_DIR]
#
#   --weights full    (the default) upstream TensorFold at engine/UPSTREAM with the opt-in patches in
#                     engine/patches: the native server and drama3-generate, in build/tensorfold
#   --weights nvfp4   the engine at engine/nvfp4/UPSTREAM, which serves the NVFP4 pruned weights
#                     (plotarmordev/drama-3-NVFP4-Pruned), unpatched: the native server, in build/tensorfold-nvfp4
#
# Environment:
#   ZIG          Zig 0.17.0 executable (default: zig on PATH)
#   NVCC         CUDA 13 nvcc (default: nvcc on PATH)
#   JOBS         parallel build jobs (default: Zig's choice)
#
# Every run checks out the pinned commit and re-applies the whole series, so the result does not depend on what an
# earlier run left behind. Output: BUILD_DIR/zig-out/native/bin/tensorfold-native, and with the full weights also
# BUILD_DIR/zig-out/bin/drama3-generate.
set -euo pipefail

repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
zig=${ZIG:-zig}
nvcc=${NVCC:-nvcc}

die() {
  echo "build-engine: $*" >&2
  exit 1
}

weights=full
if [[ ${1:-} == --weights ]]; then
  (($# >= 2)) || die "--weights needs full or nvfp4"
  weights=$2
  shift 2
elif [[ ${1:-} == --weights=* ]]; then
  weights=${1#--weights=}
  shift
fi
(($# <= 1)) || die "usage: scripts/build-engine.sh [--weights full|nvfp4] [BUILD_DIR]"
case $weights in
  full) pin=$repo/engine/UPSTREAM build=${1:-$repo/build/tensorfold} targets=(native drama3-generate) ;;
  nvfp4) pin=$repo/engine/nvfp4/UPSTREAM build=${1:-$repo/build/tensorfold-nvfp4} targets=(native) ;;
  *) die "--weights must be full or nvfp4, not '$weights'" ;;
esac

# shellcheck source=../engine/UPSTREAM
. "$pin"
[[ -n ${TENSORFOLD_REPOSITORY:-} && -n ${TENSORFOLD_COMMIT:-} ]] || die "$pin must set TENSORFOLD_REPOSITORY and TENSORFOLD_COMMIT"

shopt -s nullglob
patches=()
if [[ $weights == full ]]; then
  patches=("$repo"/engine/patches/*.patch)
  ((${#patches[@]})) || die "engine/patches has no *.patch files"
fi

command -v git >/dev/null || die "git not found"
zig=$(command -v "$zig") || die "Zig not found; set ZIG"
nvcc=$(command -v "$nvcc") || die "nvcc not found; set NVCC"

if [[ -e $build ]]; then
  git -C "$build" rev-parse --git-dir >/dev/null 2>&1 || die "$build exists and is not a git checkout"
  [[ -z $(git -C "$build" status --porcelain --untracked-files=no) ]] || die "$build has local changes; refusing to discard them"
  origin=$(git -C "$build" remote get-url origin 2>/dev/null || true)
  [[ $origin == "$TENSORFOLD_REPOSITORY" ]] || die "$build is a checkout of '$origin', not $TENSORFOLD_REPOSITORY; pass another BUILD_DIR"
  git -C "$build" am --abort >/dev/null 2>&1 || true
else
  git clone --quiet --no-checkout "$TENSORFOLD_REPOSITORY" "$build"
fi
git -C "$build" cat-file -e "$TENSORFOLD_COMMIT^{commit}" 2>/dev/null || git -C "$build" fetch --quiet origin "$TENSORFOLD_COMMIT"
git -C "$build" checkout --quiet --detach "$TENSORFOLD_COMMIT"

# A fixed committer and dates taken from the patches make the patched HEAD the same on every run.
if ((${#patches[@]})); then
  GIT_COMMITTER_NAME=build-engine GIT_COMMITTER_EMAIL=build-engine@example.invalid \
    git -C "$build" am --quiet --committer-date-is-author-date "${patches[@]}" \
    || { git -C "$build" am --abort || true; die "the patch series does not apply to $TENSORFOLD_COMMIT"; }
fi

want=$(<"$build/.zig-version")
have=$("$zig" version)
[[ $have == "$want" ]] || die "Zig $have found; the engine pins $want"

cd "$build"
"$zig" build "${targets[@]}" -Dnvcc="$nvcc" --summary all ${JOBS:+-j"$JOBS"}

echo "engine ($weights weights): $TENSORFOLD_COMMIT + ${#patches[@]} patches = $(git rev-parse HEAD)"
if [[ $weights == full ]]; then
  sha256sum zig-out/native/bin/tensorfold-native zig-out/bin/drama3-generate
else
  sha256sum zig-out/native/bin/tensorfold-native
fi
