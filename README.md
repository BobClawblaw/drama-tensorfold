# drama-tensorfold

[![code: Apache-2.0](https://img.shields.io/badge/code-Apache--2.0-0969da?style=flat-square)](LICENSE)
[![model: FACL v1.0](https://img.shields.io/badge/model-FACL_v1.0-8250df?style=flat-square)](https://huggingface.co/fishaudio/drama-3/blob/e0a9218aa48888270f06ef1ed9ea67622c0e17d2/LICENSE)
[![GPU: GB10 sm_121](https://img.shields.io/badge/GPU-GB10_sm__121-76b900?style=flat-square)](#quickstart)
[![CUDA 13](https://img.shields.io/badge/CUDA-13-76b900?style=flat-square)](#quickstart)
[![status: testing, not qualified](https://img.shields.io/badge/status-testing%2C_not_qualified-a16207?style=flat-square)](#status)

**Fish Audio's Drama 3 text-to-speech, about 1.5x faster on an NVIDIA GB10, on TensorFold's native Zig/CUDA engine.**

This repository patches [TensorFold](https://github.com/ashhart/TensorFold) to run Drama 3. It builds the engine
and starts a local speech server with an OpenAI-style `/v1/audio/speech` route, whole or streamed. It also holds
every benchmark and accuracy check behind the numbers below.

**Built with Fish Audio.** The model weights are not in this repository; you download them from
[Hugging Face](https://huggingface.co/fishaudio/drama-3) under Fish Audio's own [license](#license).

| I want to... | Use | What you get |
|---|---|---|
| Run Drama 3 on my GB10 | [Quickstart](#quickstart) ![Ready to try](https://img.shields.io/badge/ready_to_try-0969da?style=flat-square) | A local speech server, first audio in about 0.14 s |
| Check the speed claims | [`bench/`](bench/README.md) ![Benchmark tools](https://img.shields.io/badge/benchmark_tools-1a7f37?style=flat-square) | Run the comparison on your machine |
| Check the accuracy | [`qualification/`](qualification/README.md) ![Not qualified](https://img.shields.io/badge/not_qualified-a16207?style=flat-square) | Every gate against the reference, with its honest result |

## Reference vs native

On the same GB10 host (DGX Spark class, CUDA 13 libraries), one engine at a time: the stock
[sglang-omni](https://github.com/sgl-project/sglang-omni) reference against the final native build. Each engine
read 24 English texts 3 times, with no failures on either. The results were independently reviewed.

| Warm, p50 | sglang-omni reference | TensorFold native | Speedup |
|---|---:|---:|---:|
| Real-time factor (lower is faster) | 0.939 | 0.634 | **1.48x** |
| Typical clip (about 8 s of audio), whole reply | 7.93 s | 4.89 s | **1.62x** |
| First audio, streaming | 0.521 s | 0.141 s | **3.7x** |
| Short texts (19–47 characters) | 2.50 s | 1.86 s | **1.35x** |
| Medium texts (114–144 characters) | 7.93 s | 4.89 s | **1.62x** |
| Long texts (283–313 characters) | 20.22 s | 12.90 s | **1.57x** |
| Process start to ready (single start, reused caches) | 254 s | 6.4 s | **39x** |

The last row is one start per engine, not a median and not disk-cold. The reference's admission and page-cache
conditions differed from native's, and that effect was not isolated. Evidence:
[`results/before-after-02/`](results/before-after-02/README.md), and where each number comes from:
[provenance](results/README.md#where-the-numbers-come-from). The speed work changed no audio: all 46 normal test
replies stayed byte-identical across the 14 speed patches.

## Quickstart

You need Linux with user systemd, CUDA 13, [Zig 0.17.0](https://ziglang.org/download/) and 88 GiB of free memory
at load (the server is capped at 54 GiB). The checkpoint alone takes about 39 GiB of disk; the engine checkout,
build and runtime caches need more.

The launcher takes your host's shared GPU lock, the one every GPU job on the machine already uses, so two models
never load at once. Set `GPU_LOCK` to that file. Only if the host has none, create one with `touch` and make
your other GPU jobs use it too.

```sh
hf download fishaudio/drama-3 --revision e0a9218aa48888270f06ef1ed9ea67622c0e17d2 --local-dir drama-3
(cd drama-3 && sha256sum -c ../recipe/checksums/checkpoint.sha256)
ZIG=/path/to/zig-0.17.0/zig NVCC=/usr/local/cuda/bin/nvcc scripts/build-engine.sh
GPU_LOCK=/path/to/your/shared/gpu.lock && mkdir -p runtime
python3 recipe/pilot.py --native-bin build/tensorfold/zig-out/native/bin/tensorfold-native \
  --checkpoint drama-3 --runtime-dir runtime --gpu-lock "$GPU_LOCK" --evidence-dir runs/pilot-01
```

When it prints `DRAMA_PILOT_READY`, synthesize from another terminal. The second command streams and plays as
it arrives:

```sh
curl -sS http://127.0.0.1:18793/v1/audio/speech -H 'Content-Type: application/json' \
  -d '{"model": "fishaudio/drama-3", "input": "The train leaves at seven fifteen."}' -o hello.wav
curl -sSN http://127.0.0.1:18793/v1/audio/speech -H 'Content-Type: application/json' \
  -d '{"model": "fishaudio/drama-3", "input": "The train leaves at seven fifteen.", "response_format": "pcm", "stream": true}' \
  | aplay -q -f S16_LE -r 44100 -c 1
```

### Try it with your coding agent

```text
Help me run Fish Audio Drama 3 locally with https://github.com/plotarmordev/drama-tensorfold on this GB10.
Read its README, recipe/README.md and the Fish Audio Community License first, and follow them.

1. Check the requirements: CUDA 13 with nvcc, Zig 0.17.0, user systemd, disk space and free memory.
2. Download fishaudio/drama-3 at the pinned revision and verify recipe/checksums/checkpoint.sha256.
3. Build the engine with scripts/build-engine.sh and start it with recipe/pilot.py on loopback.
4. Synthesize one sentence as WAV, then stream it, and tell me the X-Finish-Reason header.

Ask me which GPU lock file this host already uses before starting, and before stopping anything already
running. Keep the server on 127.0.0.1. Letting other people send text to it can be a Hosted Service under
the license's Section III(c), which needs a separate license from Fish Audio.
```

<details>
<summary>HTTP contract</summary>

`POST /v1/audio/speech` takes `model` (`fishaudio/drama-3`), `input` (at most 4096 characters), `voice`
(`default` only), `response_format` (`wav` or `pcm`) and `stream` (`true` needs `pcm`). Anything else is
refused.

- **Whole reply:** `Content-Length` framing and an `X-Finish-Reason: stop` or `length` header.
- **Streamed reply:** chunked mono 16-bit 44.1 kHz PCM, sent as whole frames. A clipped stream ends with an
  `X-Finish-Reason: length` trailer.
- **`length`:** the reply hit the 1024-frame (47.55 s) cap without an end of speech; the audio is clipped.
- **Errors:** `400` for a refused request, `503` while the single engine slot is busy, `500` for a server fault.
</details>

## Status

> [!WARNING]
> **Testing, not qualified.** Native is faster but does not meet these accuracy bars against the reference:
> - backbone worst-row cosine 0.8006 (bar 0.8713, derived from the reference's own variance), all-row cosine
>   0.99233 (bar 0.999), last-row cosine 0.99670 (bar 0.999), hidden-state relative L2 0.124 (bar 0.05);
> - semantic KL 0.024 (bar 0.01) and top-30 overlap 0.867 (bar 0.9);
> - one-frame codec decode 33.1 dB (bar 40 dB);
> - a 7-row tower top-1 that differs where the reference's logits tie.
>
> **Long text:** both engines can pad a reply with silence up to the 47.55 s cap. One test text (long-05) never
> reaches an end of speech on native. Native returns the clipped audio, marked `X-Finish-Reason: length`.

One rater preferred native in 4 of 5 listening pairs; one pair was not blind. This does not change
qualification. Every gate and result is in [`results/`](results/README.md).

## License

**Built with Fish Audio.** All code here is [Apache-2.0](LICENSE), including the engine patches and their codec.
The Drama 3 model weights and codec checkpoint are under the
[Fish Audio Community License v1.0](https://huggingface.co/fishaudio/drama-3/blob/e0a9218aa48888270f06ef1ed9ea67622c0e17d2/LICENSE)
and are downloaded separately; [NOTICE](NOTICE) has the attributions.

<details>
<summary>What FACL v1.0 allows for the weights (a summary, not legal advice: read the license)</summary>

- **Research and non-commercial use is free** (II), including personal use and evaluation.
- **Commercial use only while your Annual Revenue is under USD 500,000** (III(a)). Annual Revenue is the gross
  revenue of you and your affiliates from all sources over the trailing twelve months. If you deploy, install
  or operate the model for a particular client, or deliver a copy to them, that client's Annual Revenue must
  also be under the threshold. That client condition does not apply to delivering only output you generated
  yourself, or to providing your own generally available product to users who don't receive a copy.
- **Reaching the threshold** (III(b)): notify business@fish.audio within 30 days. The commercial uses you were
  already making on that date may continue for 90 days. After that, commercial use needs a separate license,
  and III(a) applies again if your revenue later falls back below the threshold.
- **No Hosted Service without a separate license**, whatever your purpose or revenue (III(c)). A Hosted Service
  lets third parties generate speech from text or audio they supply, for example through an API. It
  excludes:
  - speech for content you create, select or control, or that your own product generates, delivered in or with
    your products or services;
  - production where you operate the model and direct each generation, delivering only finished output without
    client self-serve or automated access;
  - a free, non-commercial research or demonstration service that is not monetized and is not offered or
    promoted as a production service or API.
- **Show "Built with Fish Audio"** where you distribute or offer anything that uses the materials. Ship the
  license and its notice with any copy (IV(a)).
- **Use restrictions** (IV(b)), which also cover outputs. Among them:
  - no speech imitating an identifiable person's voice without their prior consent (a parent's or guardian's for
    a minor, the rights holder's for a deceased person) or another legal right to do so;
  - no impersonation to deceive, defraud or harass, and no calls that break telemarketing or robocall laws;
  - no generating sexual content involving a minor or a voice presented as a minor's, or sexual content using a
    real person's voice without that person's consent;
  - no intentionally removing, disabling, circumventing or obscuring watermark or provenance signals applied by
    the materials, or distributing tools, derivative works or services designed to do so; ordinary editing,
    mixing, compression or format conversion without that intent is not a breach;
  - if you offer speech generation to third parties, bind them to enforceable terms at least as protective;
  - no using the materials or outputs to create, train, distill or improve another foundational generative AI
    model or speech, audio or voice generation model. Fish Audio's own Models (Drama 3 and its codec) and their
    Derivative Works are excluded, and training solely to detect synthetic audio, verify watermarks or prevent
    spoofing is allowed.

  A breach of IV(b) ends the license automatically (IV(f)).
</details>

[Recipe](recipe/README.md) · [Benchmarks](bench/README.md) · [Qualification](qualification/README.md) · [Results](results/README.md) · [NOTICE](NOTICE) · [Apache 2.0 license](LICENSE) · [Model license (FACL v1.0)](https://huggingface.co/fishaudio/drama-3/blob/e0a9218aa48888270f06ef1ed9ea67622c0e17d2/LICENSE)
