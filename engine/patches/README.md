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
| 0040 | Backbone full attention runs the reference's 64-key softmax tiles and arithmetic: closer to the reference, about 5% slower on our GB10, our corpus ([results](../../results/backbone-attention-tiles.json)) |
| 0041–0044 | A stream's silence guard hears each chunk before sending it, so a stream and a whole reply cut at the same frame ([results](../../results/stream-silence-cut.json)); long-form trailers formatted without allocating; the changelog scopes the 0040–0041 measurements |
| 0045–0053 | Voice cloning tools: a voice file says whose voice it is in `source`, which `--voices` requires; a clip preparation tool with heuristic gates; `GET /v1/voices`; and `tensorfold-native voice encode`, a native CUDA codec encoder ([results](../../results/native-voice-encoder.json)) |
| 0054 | Clip preparation tells two speakers apart by timbre instead of pitch, with an empirical threshold set on model-invented voices ([results](../../results/clip-speaker-check.json)) |
| 0055–0057 | The silence guard's floor is -40 dBFS, so a reply that collapses into a steady hum ends too ([results](../../results/silence-guard-floor.json)) |

`SHA256SUMS` pins every patch.
