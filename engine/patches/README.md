# Engine patch series

The `*.patch` files here are the Drama 3 engine series, made with `git format-patch` from the engine
branch against the commit pinned in [`../UPSTREAM`](../UPSTREAM). `scripts/build-engine.sh` applies
them in file-name order with `git am`.

The codec files these patches create are under the Fish Audio Community License v1.0
([`../../LICENSES/FACL-1.0.md`](../../LICENSES/FACL-1.0.md)); everything else in them is Apache-2.0. The
[`NOTICE`](../../NOTICE) lists the files.

| Patches | What they add |
|---|---|
| 0001–0011 | The Drama 3 port: allocation cap, backbone, tower, codec, speech engine API, native host, `POST /v1/audio/speech`, oracle tools, build wiring |
| 0012–0016 | Streaming: incremental codec decode, bit-identical to the whole decode, and `stream: true` raw PCM |
| 0017–0030 | Speed, each with byte-identical audio: GEMV weight staging, fused glue, tower attention and sampling, direct-read loading, codec init thread, tower GEMV, programmatic dependent launch. 0018 returns clipped audio at `max_frames` with `X-Finish-Reason: length` |

`SHA256SUMS` pins every patch.
