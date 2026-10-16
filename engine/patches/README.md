# Engine patch series

The `*.patch` files here are the Drama 3 engine series, made with `git format-patch` from the engine
branch against the commit pinned in [`../UPSTREAM`](../UPSTREAM). `scripts/build-engine.sh` applies
them in file-name order with `git am`.

The codec files these patches create are under the Fish Audio Community License v1.0
([`../../LICENSES/FACL-1.0.md`](../../LICENSES/FACL-1.0.md)); everything else in them is Apache-2.0. The
[`NOTICE`](../../NOTICE) lists the files.
