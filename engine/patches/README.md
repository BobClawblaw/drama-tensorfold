# Engine patch series

The `*.patch` files here are opt-in patches made with `git format-patch` against the upstream TensorFold commit
pinned in [`../UPSTREAM`](../UPSTREAM). `scripts/build-engine.sh` applies them in file-name order with `git am`.
Each one is a feature branch's net diff over the patches before it; the list, the flag each adds and the upstream
pull request that carries it are in the [README](../../README.md#the-patches).

All patches are Apache-2.0 ([`../../LICENSE`](../../LICENSE)). The Drama 3 model weights and codec checkpoint the
engine loads are under the Fish Audio Community License v1.0 and are downloaded separately; see
[`NOTICE`](../../NOTICE).

`SHA256SUMS` pins every patch.
