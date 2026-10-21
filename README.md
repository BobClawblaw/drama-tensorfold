# drama-tensorfold

> [!IMPORTANT]
> **Being tested.** The recipe now builds upstream TensorFold plus opt-in patches instead of the old patched engine.
> An end-to-end comparison against the previous engine is running; this note goes once it completes.

[![code: Apache-2.0](https://img.shields.io/badge/code-Apache--2.0-0969da?style=flat-square)](LICENSE)
[![model: FACL v1.0](https://img.shields.io/badge/model-FACL_v1.0-8250df?style=flat-square)](https://huggingface.co/fishaudio/drama-3/blob/e0a9218aa48888270f06ef1ed9ea67622c0e17d2/LICENSE)
[![GPU: GB10 sm_121](https://img.shields.io/badge/GPU-GB10_sm__121-76b900?style=flat-square)](#quickstart)
[![CUDA 13](https://img.shields.io/badge/CUDA-13-76b900?style=flat-square)](#quickstart)
[![status: being tested](https://img.shields.io/badge/status-being_tested-a16207?style=flat-square)](#the-patches)

**Fish Audio's Drama 3 text-to-speech on an NVIDIA GB10, on TensorFold's native Zig/CUDA engine.**

[TensorFold](https://github.com/ashhart/TensorFold) runs Drama 3 natively since v1.1.0. This repository pins
upstream TensorFold and adds a small series of opt-in patches. It builds the engine and starts a local speech
server with an OpenAI-style `/v1/audio/speech` route, whole or streamed.

**Built with Fish Audio.** The model weights are not in this repository; you download them from
[Hugging Face](https://huggingface.co/fishaudio/drama-3) under Fish Audio's own [license](#license).

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

`scripts/build-engine.sh` checks out the commit pinned in [`engine/UPSTREAM`](engine/UPSTREAM), applies
[`engine/patches`](engine/patches) in order and builds `tensorfold-native` and `drama3-generate`.

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
(`default`, or a name loaded with `--voices`), `response_format` (`wav` or `pcm`) and `stream` (`true` needs
`pcm`). Request-supplied references and other synthesis modifiers are refused. `GET /v1/voices` lists the voices.

- **Whole reply:** `Content-Length` framing and an `X-Finish-Reason` header: `stop`, `length` or, with the silence
  guard on, `silence`.
- **Streamed reply:** chunked mono 16-bit 44.1 kHz PCM. A reply that ends in `length` or `silence` ends with an
  `X-Finish-Reason` trailer.
- **`length`:** the reply hit the frame cap (1024 frames, 47.55 s, unless `--max-frames` sets another) without an
  end of speech; the audio is clipped.
- **Errors:** `400` for a refused request, `503` while the engine is busy, `500` for a server fault.
</details>

## The patches

Upstream TensorFold already serves Drama 3. Each patch below adds one feature that stays off until you pass its
flag, so a server started without them answers as upstream does. The exceptions are the first two: batched
prefill is on by default (`TF_DRAMA_PREFILL_ROWS=1` restores upstream's single-row prefill) and the replay fix is
a bug fix. The patches stack and apply in order; each one's notes are in the engine tree's `CHANGELOG.md` or
`docs/`.

| Patch | Adds | Opt in with | Upstream |
|---|---|---|---|
| 0001 (K0) | CUDA prompt prefill in bounded row chunks | on by default; `TF_DRAMA_PREFILL_ROWS` | [#1120](https://github.com/ashhart/TensorFold/pull/1120) |
| 0002 | Replay waits for poison fills before buffers are reused | always on | [#1119](https://github.com/ashhart/TensorFold/pull/1119) |
| 0003 (K1) | A configurable frame budget | `--max-frames N` | [#1134](https://github.com/ashhart/TensorFold/pull/1134) |
| 0004 (K7) | An allowlist for bracketed speech controls | `--allowed-controls LIST` | to be proposed |
| 0005 (K9) | Attested voice catalogs and `GET /v1/voices` | `--voices DIR`, `--default-voice NAME` | [#1135](https://github.com/ashhart/TensorFold/pull/1135) |
| 0006 (K2) | A sustained-silence guard that ends a reply as `silence` | `--silence-floor-dbfs`, `--silence-seconds` | to be proposed |
| 0007 (K3) | The guard's onset rule: silence before enough voiced audio | `--silence-onset-s`, `--silence-onset-voiced-s` | to be proposed |
| 0008 (K4) | The guard's mid rule: an ending lost in a long silence | `--silence-mid-s`, `--silence-mid-min-voiced-s` | to be proposed |
| 0009 (K5) | Whole replies the guard ended are drawn again | `--silence-redraws N`, `--silence-redraw-budget-s`, `--silence-redraw-controls` | to be proposed |
| 0010 (K6) | Whole replies that stopped short of their text are drawn again | `--short-reply-ratio`, `--short-reply-chars-per-s` | to be proposed |
| 0011 (K8) | A whole reply is drawn once more when a phrase opens far above the others | `--register-redraw-st`, `--register-redraw-high`, `--register-high-hz` | to be proposed |

Pass serve flags to the launcher after `--`. An illustrative launch with the frame budget, the silence guard and
one redraw; the numbers are examples, not tuned values, so calibrate thresholds on your own voice:

```sh
python3 recipe/pilot.py … -- --max-frames 2048 --silence-floor-dbfs -50 --silence-seconds 6 --silence-redraws 1
```

Patch 0004's cue list holds only words from Fish Audio's public tags; deployments may extend the cue list locally.

A voice catalog is a directory of `drama3-http-voice/1` files, each with a `source` attestation (`synthetic`,
`self` or `consented`); the format is in `docs/drama-http-voices.md` in the engine tree. Clone only a voice the
model invented, your own, or one whose owner has consented on record, as the model license requires
([License](#license), IV(b)). `clips/` and `voices/` are git-ignored here. `recipe/pilot.py` runs the server in
`--runtime-dir`, so pass `--voices` an absolute path.

## Legacy: the patched engine

Before upstream shipped Drama 3, this recipe built its own port: 59 patches on TensorFold `c7137bb3`, last at
commit [`0f54000`](https://github.com/plotarmordev/drama-tensorfold/tree/0f54000374831db1023791a5c4b9f0b98e9cff18).
That engine's speed comparison against the sglang-omni reference, its accuracy gates, `--long-form` and its voice
cloning tools (`drama_voice_clip.py`, `drama_voice.py`, `tensorfold-native voice encode`) are not in the new base.
[`qualification/`](qualification/README.md) and [`results/`](results/README.md) measure that engine; check out
`0f54000` to rebuild it.

## License

**Built with Fish Audio.** All code here is [Apache-2.0](LICENSE), including the engine patches.
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
