# Changelog

## Unreleased

### Added

- Every speed or quality claim in a pull request carries before/after evidence from the recipe's bench and
  qualification scripts, measured against the recipe baseline (`CONTRIBUTING.md`, pull request template).
- A speed claim also carries Grill v0.11.0 speech evidence: A, B and A2 captures of the recipe server and a
  `grill-perf media compare` that passes on first-audio time and duration ratio (`CONTRIBUTING.md`, pull request
  template). Quality claims keep the WER and speaker-cosine evidence, which the Grill doesn't measure yet.
