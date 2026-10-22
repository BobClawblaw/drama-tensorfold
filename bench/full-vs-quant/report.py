#!/usr/bin/env python3
"""Tables, neutral raw records and charts for results/full-vs-quant-01 from a scored run.py run.

Reads RUN_DIR (preflight.json, ARM/sSALT/{whole,stream,pilot,health.jsonl}, scores.jsonl, pairs.jsonl) and writes
OUT_DIR/tables.json, OUT_DIR/tables.md, OUT_DIR/raw/*.jsonl and OUT_DIR/charts/*.png. Raw records keep numbers,
item ids and body hashes only: no audio, transcripts of private material, host paths or process identities.

Usage: report.py RUN_DIR OUT_DIR
"""
import json
import math
import random
import re
import sys
from pathlib import Path
from statistics import mean, median

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402

GIB = 2 ** 30
RATE, FRAME = 44100, 2048
LABELS = {'F': 'Full FP8', 'Q': 'Quant NVFP4, γ 1.5', 'FG': 'Full FP8, γ 1.5',
          'FB': 'Full FP8, built-in voice', 'QB': 'Quant NVFP4, built-in voice'}
COLORS = {'F': '#4c72b0', 'Q': '#dd8452', 'FG': '#8da0cb', 'FB': '#4c72b0', 'QB': '#dd8452'}
PAIRS = (('Q', 'F'), ('FG', 'F'), ('Q', 'FG'), ('QB', 'FB'))
KV = re.compile(r'(\w+)=([^\s]+)')


def jl(path):
    return [json.loads(l) for l in Path(path).read_text().splitlines() if l.strip()]


def num(v):
    try:
        return float(v)
    except ValueError:
        return {'true': True, 'false': False}.get(v, v)


def engine_lines(log):
    """Per-request engine records from the server log, in order: the synthesis line, then the speech line."""
    synth, speech = [], []
    for line in Path(log).read_text(errors='replace').splitlines():
        if line.startswith('info: drama: synthesis'):
            synth.append({k: num(v) for k, v in KV.findall(line)})
        elif line.startswith('[tensorfold] speech ') and ' prompt=' in line:
            speech.append({k: num(v) for k, v in KV.findall(line)})
    loaded = re.search(r'loaded in ([0-9.]+)s', Path(log).read_text(errors='replace'))
    return synth, speech, float(loaded.group(1)) if loaded else None


def bootstrap_mean_ci(by_item, n=10000, seed=20261022):
    """95 % percentile interval of the mean of per-item values, resampling items."""
    items = list(by_item)
    rng = random.Random(seed)
    means = sorted(mean(v for i in (rng.choice(items) for _ in items) for v in by_item[i]) for _ in range(n))
    return [means[int(0.025 * n)], means[int(0.975 * n) - 1]]


def mcnemar_exact(b, c):
    """Two-sided exact McNemar p for discordant counts b and c."""
    k, n = min(b, c), b + c
    if n == 0:
        return 1.0
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n)


def arm_record(run, arm, preflight):
    salts = sorted(run.joinpath(arm).glob('s*'))
    s0 = run / arm / 's0'
    whole = json.loads((s0 / 'whole' / 'summary.json').read_text())
    stream = json.loads((s0 / 'stream' / 'summary.json').read_text())
    loads, engine_loads, peaks, host_drop, raw, engine_raw = [], [], [], [], [], []
    prefill_rate, decode_rate, first_frame = [], [], []
    for sd in salts:
        salt = int(sd.name[1:])
        loads.append(json.loads((sd / 'pilot' / 'ready.json').read_text())['cold_ready_s'])
        synth, speech, loaded = engine_lines(sd / 'pilot' / 'server.log')
        engine_loads.append(loaded)
        health = [h['health'] for h in jl(sd / 'health.jsonl') if 'health' in h]
        for kind in ('whole', 'stream'):
            if (sd / kind / 'server-after.json').exists():
                after = json.loads((sd / kind / 'server-after.json').read_text())
                body = after['health'].get('body')
                if isinstance(body, str):
                    try:
                        body = json.loads(body)
                    except ValueError:
                        body = None
                if isinstance(body, dict) and 'memory' in body:
                    health.append(body)
        peaks.append(max(h['memory']['peak'] for h in health if 'memory' in h))
        mem = jl(sd / 'pilot' / 'memory.jsonl')
        if mem:
            host_drop.append(mem[0]['memavailable_bytes'] - min(m['memavailable_bytes'] for m in mem))
        samples = {k: jl(sd / k / 'samples.jsonl') for k in ('whole', 'stream') if (sd / k / 'samples.jsonl').exists()}
        by_format = {'wav': [s for s in speech if s.get('format') == 'wav'],
                     'pcm': [s for s in speech if s.get('format') == 'pcm']}
        for kind, rows in samples.items():
            lines = by_format['wav' if kind == 'whole' else 'pcm']
            matched = len(lines) == len(rows)
            for i, s in enumerate(rows):
                audio_s = s['audio']['duration_s'] if s.get('audio') else None
                rec = {'arm': arm, 'salt': salt, 'run': kind, 'phase': s['phase'], 'round': s['round'],
                       'item': s['item'], 'outcome': s['outcome'], 'total_s': s['total_s'],
                       'first_frame_s': s.get('first_frame_s'), 'audio_s': audio_s, 'rtf': s.get('rtf'),
                       'body_sha256': s.get('body_sha256'),
                       'prompt_tokens': int(lines[i]['prompt']) if matched else None}
                raw.append(rec)
                if kind == 'stream' and s['phase'] == 'warm' and s['outcome'] == 'ok' and s.get('first_frame_s'):
                    frames = audio_s * RATE / FRAME
                    first_frame.append(s['first_frame_s'])
                    decode_rate.append((frames - 1) / (s['total_s'] - s['first_frame_s']))
                    if matched:
                        prefill_rate.append(int(lines[i]['prompt']) / s['first_frame_s'])
        for i, line in enumerate(synth):
            engine_raw.append({'arm': arm, 'salt': salt, 'seq': i, **{k: v for k, v in line.items()
                                                                       if k not in ('speech',)}})
    gauges = [h['live'] for sd in salts for h in (x['health'] for x in jl(sd / 'health.jsonl') if 'health' in x)
              if 'live' in h]
    ckpt = preflight['arms'][arm]['checkpoint']
    size = preflight['checkpoints'][ckpt]
    warm, swarm = whole['phases']['warm'], stream['phases']['warm']
    rec = {
        'label': LABELS[arm], 'checkpoint': ckpt, 'flags': preflight['arms'][arm]['flags'],
        'reference_voice': preflight['arms'][arm]['reference_voice'],
        'weights_and_codec_bytes': size['weights_and_codec_bytes'], 'checkpoint_total_bytes': size['total_bytes'],
        'device_peak_bytes': {'max': max(peaks), 'per_start': peaks},
        'host_memavailable_drop_bytes': {'max': max(host_drop) if host_drop else None, 'per_start': host_drop},
        'cold_ready_s': {'per_start': loads, 'median': median(loads)},
        'engine_loaded_in_s': {'per_start': engine_loads, 'median': median(x for x in engine_loads if x is not None)},
        'whole_warm': {'attempted': warm['attempted'], 'succeeded': warm['succeeded'],
                       'end_to_end_s_p50': warm['end_to_end_s']['ok_only']['p50'],
                       'end_to_end_s_p95': warm['end_to_end_s']['ok_only']['p95'],
                       'rtf_p50': warm['realtime_factor']['ok_only']['p50'],
                       'rtf_p95': warm['realtime_factor']['ok_only']['p95'],
                       'rtf_mean': warm['realtime_factor']['ok_only']['mean'],
                       'audio_s_total': warm['audio_s']['total']},
        'whole_cold_first_request_s': whole['phases']['cold']['end_to_end_s']['ok_only'].get('p50'),
        'stream_warm': {'attempted': swarm['attempted'], 'succeeded': swarm['succeeded'],
                        'first_frame_s_p50': swarm['first_frame_s']['ok_only']['p50'],
                        'first_frame_s_p95': swarm['first_frame_s']['ok_only']['p95'],
                        'decode_frames_per_s_median': median(decode_rate) if decode_rate else None,
                        'prompt_tokens_per_s_to_first_frame_median': median(prefill_rate) if prefill_rate else None,
                        'prompt_tokens_median': median(r['prompt_tokens'] for r in raw if r['prompt_tokens'])
                        if any(r['prompt_tokens'] for r in raw) else None},
        'health_gauges_max': {'prefill_tokens_per_second': max((g.get('prefill_tokens_per_second') or 0) for g in gauges),
                              'decode_tokens_per_second': max((g.get('decode_tokens_per_second') or 0) for g in gauges)},
    }
    return rec, raw, engine_raw


def quality(scores, pairs, arms):
    out = {}
    for arm in arms:
        rows = [r for r in scores if r['arm'] == arm]
        ok = [r for r in rows if not r.get('missing')]
        by_item = {}
        for r in ok:
            by_item.setdefault(r['item'], []).append(r['wer'])
        sims = [p['cosine'] for p in pairs if p['kind'] == 'arm_vs_full' and p['arm'] == arm]
        out[arm] = {'takes': len(rows), 'missing': len(rows) - len(ok),
                    'failed': sum(bool(r['failed']) for r in rows), 'capped': sum(bool(r.get('capped')) for r in ok),
                    'collapsed': sum(bool(r.get('collapsed')) for r in ok),
                    'wer_mean': mean(r['wer'] for r in ok), 'wer_mean_ci95': bootstrap_mean_ci(by_item),
                    'wer_pooled': sum(r['wer'] * r['ref_words'] for r in ok) / sum(r['ref_words'] for r in ok),
                    'wer_median': median(r['wer'] for r in ok),
                    'quiet_run_s_max': max(r['quiet_run_s'] for r in ok),
                    'audio_s_mean': mean(r['audio_s'] for r in ok),
                    'speaker_cosine_vs_full_mean': mean(sims) if sims else None}
    for base in sorted({p['arm'] for p in pairs if p['kind'] == 'full_across_salts'}):
        sims = [p['cosine'] for p in pairs if p['kind'] == 'full_across_salts' and p['arm'] == base]
        out[base]['speaker_cosine_same_model_across_salts_mean'] = mean(sims)
    paired = {}
    index = {(r['arm'], r['salt'], r['item']): r for r in scores}
    for a, b in PAIRS:
        keys = [(s, i) for (x, s, i) in index if x == a and (b, s, i) in index]
        if not keys:
            continue
        fa = [bool(index[(a, s, i)]['failed']) for s, i in keys]
        fb = [bool(index[(b, s, i)]['failed']) for s, i in keys]
        only_a = sum(x and not y for x, y in zip(fa, fb))
        only_b = sum(y and not x for x, y in zip(fa, fb))
        diff = {}
        for s, i in keys:
            ra, rb = index[(a, s, i)], index[(b, s, i)]
            if not ra.get('missing') and not rb.get('missing'):
                diff.setdefault(i, []).append(ra['wer'] - rb['wer'])
        paired[f'{a}_vs_{b}'] = {'pairs': len(keys), 'failed_only_' + a: only_a, 'failed_only_' + b: only_b,
                                 'mcnemar_exact_p': mcnemar_exact(only_a, only_b),
                                 'wer_diff_mean': mean(v for vs in diff.values() for v in vs),
                                 'wer_diff_ci95_items': bootstrap_mean_ci(diff)}
    return out, paired


def charts(tables, out):
    out.mkdir(parents=True, exist_ok=True)
    arms = [a for a in ('F', 'FG', 'Q') if a in tables['arms']]
    built = [a for a in ('FB', 'QB') if a in tables['arms']]
    A = tables['arms']
    Qy = tables['quality']

    def bars(ax, names, values, title, unit, fmt='{:.2f}'):
        xs = range(len(names))
        b = ax.bar(xs, values, color=[COLORS[n] for n in names], hatch=None)
        for n, rect in zip(names, b):
            if n in ('FG',) or n.endswith('B'):
                rect.set_hatch('//' if n == 'FG' else '..')
        ax.set_xticks(list(xs), [LABELS[n].replace(', ', ',\n') for n in names], fontsize=8)
        ax.set_title(title, fontsize=10)
        ax.set_ylabel(unit, fontsize=9)
        for x, v in zip(xs, values):
            ax.annotate(fmt.format(v), (x, v), ha='center', va='bottom', fontsize=8)
        ax.margins(y=0.15)

    fig, axes = plt.subplots(1, 2, figsize=(9, 3.6))
    fq = [a for a in ('F', 'Q') if a in A]
    bars(axes[0], fq, [A[a]['weights_and_codec_bytes'] / GIB for a in fq], 'Weights + codec on disk', 'GiB', '{:.1f}')
    bars(axes[1], arms, [A[a]['device_peak_bytes']['max'] / GIB for a in arms], 'Peak device memory (/health)', 'GiB',
         '{:.1f}')
    fig.suptitle('Drama 3 on one GB10: footprint', fontsize=11)
    fig.tight_layout()
    fig.savefig(out / 'footprint.png', dpi=150)
    plt.close(fig)

    names = arms + built
    fig, axes = plt.subplots(1, 4, figsize=(15, 3.8))
    bars(axes[0], names, [A[a]['whole_warm']['rtf_p50'] for a in names], 'Real-time factor, p50 (lower is faster)',
         'RTF')
    bars(axes[1], names, [A[a]['stream_warm']['first_frame_s_p50'] for a in names], 'First audio when streaming, p50',
         's')
    bars(axes[2], names, [A[a]['stream_warm']['decode_frames_per_s_median'] for a in names],
         'Decode, codec frames/s (median)', 'frames/s', '{:.1f}')
    bars(axes[3], names, [A[a]['cold_ready_s']['median'] for a in names], 'Process start to ready (cold disk)', 's',
         '{:.1f}')
    fig.suptitle('Speed: one engine binary, 24-item corpus, concurrency 1', fontsize=11)
    fig.tight_layout()
    fig.savefig(out / 'speed.png', dpi=150)
    plt.close(fig)

    fig, axes = plt.subplots(1, 3, figsize=(12, 3.8))
    wer = [Qy[a]['wer_mean'] * 100 for a in names]
    bars(axes[0], names, wer, 'Word error rate, Whisper large-v3 (mean)', '%', '{:.1f}')
    for x, a in enumerate(names):
        lo, hi = Qy[a]['wer_mean_ci95']
        axes[0].errorbar(x, Qy[a]['wer_mean'] * 100, yerr=[[Qy[a]['wer_mean'] * 100 - lo * 100],
                                                           [hi * 100 - Qy[a]['wer_mean'] * 100]], fmt='none',
                         ecolor='k', capsize=3, lw=1)
    bars(axes[1], names, [Qy[a]['failed'] / Qy[a]['takes'] * 100 for a in names], 'Failed takes (cap, WER > 0.2 '
         'or ≥ 3 s stall)', '% of takes', '{:.1f}')
    sim = [a for a in names if Qy[a].get('speaker_cosine_vs_full_mean') is not None]
    bars(axes[2], sim, [Qy[a]['speaker_cosine_vs_full_mean'] for a in sim], 'Speaker similarity to the full\nmodel\'s '
         'take (ECAPA cosine)', 'cosine', '{:.3f}')
    for base, ls in (('F', '--'), ('FB', ':')):
        v = Qy.get(base, {}).get('speaker_cosine_same_model_across_salts_mean')
        if v is not None:
            axes[2].axhline(v, color='k', ls=ls, lw=1, label=f'{LABELS[base]} vs itself, other salt')
    axes[2].legend(fontsize=7, loc='lower right')
    axes[2].set_ylim(0, 1.05)
    fig.suptitle('Quality: 24 items × 4 salts per arm', fontsize=11)
    fig.tight_layout()
    fig.savefig(out / 'quality.png', dpi=150)
    plt.close(fig)


def markdown(t):
    A, Qy, P = t['arms'], t['quality'], t['paired']
    names = [a for a in ('F', 'Q', 'FG', 'FB', 'QB') if a in A]
    head = '| Measure | ' + ' | '.join(LABELS[a] for a in names) + ' |\n|---|' + '---:|' * len(names) + '\n'

    def row(name, f):
        return f'| {name} | ' + ' | '.join(f(a) for a in names) + ' |\n'
    g = lambda b: f'{b / GIB:.2f}'  # noqa: E731
    md = head
    md += row('Weights + codec on disk (GiB)', lambda a: g(A[a]['weights_and_codec_bytes']))
    md += row('Peak device memory, /health (GiB)', lambda a: g(A[a]['device_peak_bytes']['max']))
    md += row('Host MemAvailable drop, max (GiB)', lambda a: g(A[a]['host_memavailable_drop_bytes']['max']))
    md += row('Process start to ready, median of 4 cold starts (s)', lambda a: f'{A[a]["cold_ready_s"]["median"]:.1f}')
    md += row('Engine load, median (s)', lambda a: f'{A[a]["engine_loaded_in_s"]["median"]:.1f}')
    md += row('Real-time factor, warm p50', lambda a: f'{A[a]["whole_warm"]["rtf_p50"]:.3f}')
    md += row('Real-time factor, warm p95', lambda a: f'{A[a]["whole_warm"]["rtf_p95"]:.3f}')
    md += row('Whole reply, warm p50 (s)', lambda a: f'{A[a]["whole_warm"]["end_to_end_s_p50"]:.2f}')
    md += row('First audio when streaming, p50 (s)', lambda a: f'{A[a]["stream_warm"]["first_frame_s_p50"]:.3f}')
    md += row('Decode, codec frames/s (median)', lambda a: f'{A[a]["stream_warm"]["decode_frames_per_s_median"]:.1f}')
    md += row('Prompt tokens per second to first audio (median)', lambda a: (
        f'{A[a]["stream_warm"]["prompt_tokens_per_s_to_first_frame_median"]:.0f}'
        if A[a]['stream_warm']['prompt_tokens_per_s_to_first_frame_median'] else '—'))
    md += row('Prompt tokens per request (median)', lambda a: (
        f'{A[a]["stream_warm"]["prompt_tokens_median"]:.0f}' if A[a]['stream_warm']['prompt_tokens_median'] else '—'))
    md += row('Warm requests succeeded', lambda a: f'{A[a]["whole_warm"]["succeeded"]}/{A[a]["whole_warm"]["attempted"]}'
              f' + {A[a]["stream_warm"]["succeeded"]}/{A[a]["stream_warm"]["attempted"]} streamed')
    md += row('Word error rate, mean [95 % CI]', lambda a: f'{Qy[a]["wer_mean"] * 100:.2f} % '
              f'[{Qy[a]["wer_mean_ci95"][0] * 100:.2f}, {Qy[a]["wer_mean_ci95"][1] * 100:.2f}]')
    md += row('Word error rate, pooled', lambda a: f'{Qy[a]["wer_pooled"] * 100:.2f} %')
    md += row('Failed takes (of 96)', lambda a: f'{Qy[a]["failed"]} (cap {Qy[a]["capped"]}, collapsed '
              f'{Qy[a]["collapsed"]})')
    md += row('Speaker cosine to the full model\'s take', lambda a: (
        f'{Qy[a]["speaker_cosine_vs_full_mean"]:.3f}' if Qy[a].get('speaker_cosine_vs_full_mean') is not None else
        f'{Qy[a]["speaker_cosine_same_model_across_salts_mean"]:.3f} (itself, other salt)'))
    md += '\n| Paired comparison | Pairs | Failed only in first | Failed only in second | Exact McNemar p | ' \
          'WER difference, mean [95 % CI over items] |\n|---|---:|---:|---:|---:|---|\n'
    for k, v in P.items():
        a, b = k.split('_vs_')
        md += (f'| {LABELS[a]} vs {LABELS[b]} | {v["pairs"]} | {v["failed_only_" + a]} | {v["failed_only_" + b]} | '
               f'{v["mcnemar_exact_p"]:.3f} | {v["wer_diff_mean"] * 100:+.2f} pp [{v["wer_diff_ci95_items"][0] * 100:+.2f}, '
               f'{v["wer_diff_ci95_items"][1] * 100:+.2f}] |\n')
    return md


def main():
    run, out = Path(sys.argv[1]), Path(sys.argv[2])
    preflight = json.loads((run / 'preflight.json').read_text())
    arms = [a for a in ('F', 'Q', 'FG', 'FB', 'QB') if (run / a / 's0' / 'whole' / 'summary.json').exists()]
    tables = {'schema': 'full-vs-quant/1', 'arms': {}, 'environment': {
        'hardware': {k: v for k, v in preflight['hardware'].items() if k != 'host'},
        'engine_build': {k: preflight['binary_build'][k] for k in ('commit', 'describe', 'branch', 'clean_tree', 'built')},
        'engine_binary_sha256': preflight['binary_sha256'], 'corpus_sha256': preflight['corpus_sha256'],
        'voice_sha256': preflight['voice_sha256'], 'harness_commit': preflight['harness_commit'],
        'checkpoint_pins_sha256': {k: v['verify']['pins_sha256'] for k, v in preflight['checkpoints'].items()},
        'checkpoint_files_verified': {k: v['verify']['files'] for k, v in preflight['checkpoints'].items()},
        'started_at': preflight['started_at'], 'salts': preflight['salts']}}
    (out / 'raw').mkdir(parents=True, exist_ok=True)
    requests, engine = [], []
    for arm in arms:
        rec, raw, eng = arm_record(run, arm, preflight)
        tables['arms'][arm] = rec
        requests += raw
        engine += eng
    scores, pairs = jl(run / 'scores.jsonl'), jl(run / 'pairs.jsonl')
    tables['quality'], tables['paired'] = quality(scores, pairs, arms)
    (out / 'raw' / 'requests.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in requests))
    (out / 'raw' / 'engine.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in engine))
    (out / 'raw' / 'scores.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in scores))
    (out / 'raw' / 'speaker-pairs.jsonl').write_text(''.join(json.dumps(p) + '\n' for p in pairs))
    (out / 'tables.json').write_text(json.dumps(tables, indent=1) + '\n')
    (out / 'tables.md').write_text(markdown(tables))
    charts(tables, out / 'charts')
    print(markdown(tables))


if __name__ == '__main__':
    main()
