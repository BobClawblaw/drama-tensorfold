# Engine patch series

The `*.patch` files here are the Drama 3 engine series, made with `git format-patch` from the engine
branch against the commit pinned in [`../UPSTREAM`](../UPSTREAM). `scripts/build-engine.sh` applies
them in file-name order with `git am`.

All patches, including the codec files they create, are Apache-2.0 ([`../../LICENSE`](../../LICENSE)). The Drama 3
model weights and codec checkpoint the engine loads are under the Fish Audio Community License v1.0 and are
downloaded separately; see [`NOTICE`](../../NOTICE).

| Patches | What they add |
|---|---|
| 0001–0011 | The Drama 3 port: allocation cap, backbone, tower, codec, speech engine API, native host, `POST /v1/audio/speech`, oracle tools, build wiring |
| 0012–0016 | Streaming: incremental codec decode, bit-identical to the whole decode, and `stream: true` raw PCM |
| 0017–0030 | Speed, each with byte-identical audio: GEMV weight staging, fused glue, tower attention and sampling, direct-read loading, codec init thread, tower GEMV, programmatic dependent launch. 0018 returns clipped audio at `max_frames` with `X-Finish-Reason: length` |
| 0031–0034 | Voice references: `references` with `vq_codes`, `--voices DIR` / `--default-voice NAME`, a prefill oracle for voice-reference rows, and the generated codes a request can keep |
| 0035–0037 | `--long-form`: long inputs in balanced segments at sentence ends, each hearing the one before, joined with room-tone pauses sized by punctuation |
| 0038–0039 | `--max-frames N` for one synthesis of up to about 190 s, and `X-Finish-Reason: silence` after 10 s of silence |

`SHA256SUMS` pins every patch.
