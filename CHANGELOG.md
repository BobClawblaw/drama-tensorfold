# Changelog

## Unreleased

### Added

- `--weights nvfp4|full` on `scripts/build-engine.sh` and `recipe/pilot.py`: the NVFP4 pruned weights serve with
  the same two commands as the full model. The build checks out the engine pinned in `engine/nvfp4/UPSTREAM`; the
  launcher downloads the pinned checkpoint on first use, checks it against `recipe/checksums/nvfp4.sha256` on every
  start, refusing missing or changed files before it takes the GPU lock, and serves it with
  `--cfg-gamma 1.5 --cfg-batched` unless a guidance flag of your own follows `--`. Without `--weights`, both behave
  as before.
- Every speed or quality claim in a pull request carries before/after evidence from the recipe's bench and
  qualification scripts, measured against the recipe baseline (`CONTRIBUTING.md`, pull request template).
- A speed claim also carries Grill v0.11.0 speech evidence: A, B and A2 captures of the recipe server and a
  `grill-perf media compare` that passes on first-audio time and duration ratio (`CONTRIBUTING.md`, pull request
  template). Quality claims keep the WER and speaker-cosine evidence, which the Grill doesn't measure yet.
