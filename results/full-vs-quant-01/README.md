# Full model against quant 01

Drama 3 full FP8 against the NVFP4 quant (routed experts GPTQ, 7,369 of 10,240 kept), on one GB10 host, one engine
binary for every arm, from run `run-01` of `bench/full-vs-quant/run.py`. Five arms, four seed salts each:

| Arm | Checkpoint | Voice | Guidance |
|---|---|---|---|
| F | full FP8 | reference voice | none |
| Q | quant | reference voice | γ 1.5, batched |
| FG | full FP8 | reference voice | γ 1.5, batched |
| FB | full FP8 | built-in voice | none |
| QB | quant | built-in voice | γ 1.5 requested; the engine logged γ 1.00 (inactive without a reference) |

| File | What it holds |
|---|---|
| [`card-section.md`](card-section.md) | The model-card section: the recipe (quant, engine, codec), the tables, the charts and the run history, including the resume |
| [`tables.md`](tables.md) | The per-arm table and the paired comparisons |
| [`tables.json`](tables.json) | Every number in the tables, the environment, the resume record and the pin change |
| [`charts/`](charts) | `footprint`, `speed` and `quality`, each as PNG and SVG |
| [`raw/`](raw) | Per-request records, engine log lines, per-take scores (with transcripts of the public bench corpus) and speaker-similarity pairs |

`tables.json` SHA-256 `fcd56bce…`, from merged scores SHA-256 `9e13c6a9…` and speaker pairs SHA-256 `88b72ca4…`
(byte-identical to `raw/scores.jsonl` and `raw/speaker-pairs.jsonl`).

## Run history

The first pass stopped at the quant's first salt: the benchmark client refused to start it because the quant's pin
list held Hugging Face download metadata (`.cache/huggingface/`) and `.gitattributes`, hidden paths the client does
not list. Commit `7f14908` dropped the metadata from the pins and gave the client the same list less hidden paths;
every kept entry has the sha256 it had before. The run resumed from that salt with the full model's four salts kept;
the refused directory was set aside and is in no number. `card-section.md` and `tables.json` carry the counts.

## How it was made

Scoring ran on a CPU host (Whisper large-v3 in float32; the GPU path uses float16), in two processes split so every
speaker pair stays inside one process: the reference-voice arms (F, Q, FG) and the built-in-voice arms (FB, QB).
Their outputs were concatenated. The run directory is a copy of the GPU host's; nothing was re-run.

```sh
mkdir -p runs/score-views/fq runs/score-views/builtin
for a in F Q FG; do ln -s ../../run-01/$a runs/score-views/fq/$a; done
for a in FB QB; do ln -s ../../run-01/$a runs/score-views/builtin/$a; done
for v in fq builtin; do
  CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=9 bench/full-vs-quant/score.py runs/score-views/$v \
    --whisper WHISPER_LARGE_V3_DIR --ecapa SPKREC_ECAPA_VOXCELEB_DIR --speechbrain-path SPEECHBRAIN_DIR &
done; wait
cat runs/score-views/{fq,builtin}/scores.jsonl > runs/run-01/scores.jsonl
cat runs/score-views/{fq,builtin}/pairs.jsonl > runs/run-01/pairs.jsonl
bench/full-vs-quant/report.py runs/run-01 results/full-vs-quant-01
```
