#!/usr/bin/env python3
"""
Generate a full HTML evaluation report from the checkpoint JSONL.
Usage:
    python scripts/generate_report.py \
        --checkpoint <path-to-checkpoint.jsonl> \
        --output <report.html>
"""
import argparse
import json
import math
import os
import sys
import html as html_mod
from datetime import datetime

# ── locate sentence_transformers ──────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SERVICE_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, SERVICE_DIR)

try:
    from sentence_transformers import SentenceTransformer
    import numpy as np
    HAS_ST = True
except ImportError:
    HAS_ST = False

# ── thresholds for pass / fail ────────────────────────────────────────────────
SIM_PASS   = 0.75   # cosine similarity ≥ this → pass
RR_PASS    = 0.33   # reciprocal rank  ≥ this  → retrieval pass  (hit in top-3)

EMBED_MODEL = os.path.join(
    SERVICE_DIR, "models", "embeddings",
    "sentence_transformers", "BAAI_bge-large-en-v1.5"
)


def compute_sims(records):
    """Return list of cosine similarity floats, one per record."""
    if not HAS_ST:
        print("[WARN] sentence_transformers not available — sim=0 for all records.")
        return [0.0] * len(records)

    model_path = EMBED_MODEL if os.path.isdir(EMBED_MODEL) else "BAAI/bge-large-en-v1.5"
    print(f"[SemanticSim] Loading {model_path} …")
    model = SentenceTransformer(model_path)

    refs  = [r.get("reference", "") or "" for r in records]
    gens  = [r.get("generated", "") or "" for r in records]

    print(f"[SemanticSim] Encoding {len(records)} pairs …")
    emb_r = model.encode(refs,  batch_size=32, show_progress_bar=True,
                          normalize_embeddings=True, convert_to_numpy=True)
    emb_g = model.encode(gens,  batch_size=32, show_progress_bar=True,
                          normalize_embeddings=True, convert_to_numpy=True)

    sims = (emb_r * emb_g).sum(axis=1).tolist()
    print(f"[SemanticSim] Done. Mean={sum(sims)/len(sims):.4f}")
    return sims


def nature_badge(nature):
    colours = {
        "direct_fact": "#2563eb",
        "temporal":    "#7c3aed",
        "spanning":    "#0891b2",
    }
    bg = colours.get(nature, "#64748b")
    return f'<span class="badge" style="background:{bg}">{html_mod.escape(nature)}</span>'


def rr_bar(rr):
    pct = int(rr * 100)
    colour = "#16a34a" if rr >= RR_PASS else "#dc2626"
    return (
        f'<div class="bar-bg"><div class="bar-fill" '
        f'style="width:{pct}%;background:{colour}"></div></div>'
        f'<span class="bar-label">{rr:.2f}</span>'
    )


def sim_bar(sim):
    pct = max(0, int(sim * 100))
    colour = "#16a34a" if sim >= SIM_PASS else "#dc2626"
    return (
        f'<div class="bar-bg"><div class="bar-fill" '
        f'style="width:{pct}%;background:{colour}"></div></div>'
        f'<span class="bar-label">{sim:.3f}</span>'
    )


def verdict_cell(rr, sim):
    if rr >= RR_PASS and sim >= SIM_PASS:
        return '<span class="verdict pass">PASS</span>'
    elif rr < RR_PASS and sim < SIM_PASS:
        return '<span class="verdict fail">FAIL</span>'
    elif rr < RR_PASS:
        return '<span class="verdict partial">NO-HIT</span>'
    else:
        return '<span class="verdict partial">LOW-SIM</span>'


def build_config_html():
    config_path = os.path.join(SERVICE_DIR, "config.yaml")
    try:
        content = open(config_path).read()
    except FileNotFoundError:
        content = "(config.yaml not found)"
    return f'<pre class="config-block">{html_mod.escape(content)}</pre>'


def build_html(records, sims, out_path):
    n = len(records)
    rrs = [r["rr"] for r in records]
    mrr = sum(rrs) / n
    hit1 = sum(1 for rr in rrs if rr >= 1.0) / n
    hit3 = sum(1 for rr in rrs if rr >= RR_PASS) / n
    mean_sim = sum(sims) / n

    # per-nature breakdown
    natures = {}
    for r, s in zip(records, sims):
        nat = r.get("nature", "unknown")
        natures.setdefault(nat, {"rrs": [], "sims": [], "pass": 0, "fail": 0})
        natures[nat]["rrs"].append(r["rr"])
        natures[nat]["sims"].append(s)
        if r["rr"] >= RR_PASS and s >= SIM_PASS:
            natures[nat]["pass"] += 1
        else:
            natures[nat]["fail"] += 1

    nature_rows = ""
    for nat, d in sorted(natures.items()):
        cnt = len(d["rrs"])
        mrr_n = sum(d["rrs"]) / cnt
        sim_n = sum(d["sims"]) / cnt
        pass_pct = d["pass"] / cnt * 100
        nature_rows += (
            f"<tr><td>{html_mod.escape(nat)}</td><td>{cnt}</td>"
            f"<td>{mrr_n:.4f}</td><td>{sim_n:.4f}</td>"
            f"<td>{d['pass']}</td><td>{d['fail']}</td>"
            f"<td>{pass_pct:.1f}%</td></tr>\n"
        )

    # question rows
    q_rows = ""
    for r, sim in zip(records, sims):
        err = html_mod.escape(r.get("error", "") or "")
        err_cell = f'<span class="error-msg">{err}</span>' if err else ""
        q_rows += f"""
<tr>
  <td class="col-id">{r['id']}</td>
  <td class="col-nat">{nature_badge(r.get('nature',''))}</td>
  <td class="col-q">{html_mod.escape(r.get('question',''))}</td>
  <td class="col-ref">{html_mod.escape(r.get('reference',''))}</td>
  <td class="col-gen">{html_mod.escape(r.get('generated','') or '')}{err_cell}</td>
  <td class="col-rr">{rr_bar(r['rr'])}</td>
  <td class="col-sim">{sim_bar(sim)}</td>
  <td class="col-time">{r.get('elapsed_chat',0):.1f}s</td>
  <td class="col-v">{verdict_cell(r['rr'], sim)}</td>
</tr>"""

    total_pass = sum(1 for r, s in zip(records, sims) if r["rr"] >= RR_PASS and s >= SIM_PASS)
    total_fail = n - total_pass

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>RAG Evaluation Report — {datetime.now().strftime('%Y-%m-%d')}</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{font-family:'Segoe UI',system-ui,sans-serif;background:#f8fafc;color:#1e293b;font-size:13px}}
  h1{{font-size:1.6rem;font-weight:700;color:#0f172a}}
  h2{{font-size:1.1rem;font-weight:600;margin-top:2rem;margin-bottom:.6rem;color:#1e40af;border-bottom:2px solid #bfdbfe;padding-bottom:.3rem}}
  .page{{max-width:1800px;margin:0 auto;padding:1.5rem}}
  .header{{background:linear-gradient(135deg,#1e3a5f,#2563eb);color:#fff;padding:1.5rem 2rem;border-radius:12px;margin-bottom:1.5rem}}
  .header h1{{color:#fff}}
  .header p{{opacity:.85;margin-top:.4rem;font-size:.9rem}}
  .meta-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:1rem;margin-bottom:1.5rem}}
  .meta-card{{background:#fff;border:1px solid #e2e8f0;border-radius:8px;padding:1rem;text-align:center;box-shadow:0 1px 3px rgba(0,0,0,.06)}}
  .meta-card .val{{font-size:1.8rem;font-weight:700;color:#2563eb}}
  .meta-card .lbl{{font-size:.75rem;color:#64748b;margin-top:.2rem}}
  .meta-card.green .val{{color:#16a34a}}
  .meta-card.red .val{{color:#dc2626}}
  table{{width:100%;border-collapse:collapse;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,.08)}}
  thead th{{background:#1e3a5f;color:#fff;padding:.6rem .8rem;text-align:left;font-weight:600;font-size:.75rem;text-transform:uppercase;letter-spacing:.04em;position:sticky;top:0;z-index:2}}
  tbody tr:nth-child(even){{background:#f8fafc}}
  tbody tr:hover{{background:#eff6ff}}
  td{{padding:.55rem .8rem;border-bottom:1px solid #e2e8f0;vertical-align:top;line-height:1.45}}
  .col-id{{width:45px;text-align:center;color:#94a3b8;font-weight:600}}
  .col-nat{{width:95px}}
  .col-q{{width:18%;min-width:180px}}
  .col-ref{{width:22%;min-width:200px;color:#475569}}
  .col-gen{{width:22%;min-width:200px}}
  .col-rr{{width:110px}}
  .col-sim{{width:110px}}
  .col-time{{width:60px;text-align:right;color:#64748b}}
  .col-v{{width:80px;text-align:center}}
  .badge{{display:inline-block;color:#fff;font-size:.7rem;padding:.15rem .5rem;border-radius:12px;font-weight:600;white-space:nowrap}}
  .bar-bg{{background:#e2e8f0;border-radius:4px;height:8px;width:80px;display:inline-block;vertical-align:middle;margin-right:4px}}
  .bar-fill{{height:100%;border-radius:4px;transition:width .3s}}
  .bar-label{{font-size:.75rem;color:#475569;vertical-align:middle}}
  .verdict{{display:inline-block;font-size:.75rem;font-weight:700;padding:.2rem .55rem;border-radius:6px}}
  .verdict.pass{{background:#dcfce7;color:#166534}}
  .verdict.fail{{background:#fee2e2;color:#991b1b}}
  .verdict.partial{{background:#fef3c7;color:#92400e}}
  .error-msg{{color:#dc2626;font-size:.75rem;font-style:italic}}
  .config-block{{background:#0f172a;color:#e2e8f0;padding:1.2rem;border-radius:8px;font-size:.8rem;overflow-x:auto;white-space:pre-wrap}}
  .summary-nat table{{max-width:700px}}
  .summary-nat td,.summary-nat th{{padding:.45rem .8rem}}
  .filters{{display:flex;gap:.8rem;margin-bottom:.8rem;align-items:center;flex-wrap:wrap}}
  .filters select,.filters input{{padding:.4rem .6rem;border:1px solid #cbd5e1;border-radius:6px;font-size:.82rem}}
  #searchInput{{width:260px}}
  .tbl-scroll{{overflow-x:auto;border-radius:8px}}
  .pass-rate-bar{{height:18px;background:#e2e8f0;border-radius:9px;overflow:hidden;margin-top:.5rem}}
  .pass-rate-fill{{height:100%;background:#16a34a;border-radius:9px}}
</style>
</head>
<body>
<div class="page">

<div class="header">
  <h1>RAG Evaluation Report</h1>
  <p>Knowledge Base: MegaRetail Hypermart &nbsp;|&nbsp; Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')} &nbsp;|&nbsp; Questions: {n}</p>
</div>

<!-- ── SUMMARY CARDS ── -->
<div class="meta-grid">
  <div class="meta-card"><div class="val">{n}</div><div class="lbl">Total Questions</div></div>
  <div class="meta-card green"><div class="val">{total_pass}</div><div class="lbl">PASS</div></div>
  <div class="meta-card red"><div class="val">{total_fail}</div><div class="lbl">FAIL / Partial</div></div>
  <div class="meta-card"><div class="val">{total_pass/n*100:.1f}%</div><div class="lbl">Overall Pass Rate</div></div>
  <div class="meta-card"><div class="val">{mrr:.4f}</div><div class="lbl">MRR</div></div>
  <div class="meta-card"><div class="val">{hit1:.4f}</div><div class="lbl">Hit@1</div></div>
  <div class="meta-card"><div class="val">{hit3:.4f}</div><div class="lbl">Hit@3</div></div>
  <div class="meta-card"><div class="val">{mean_sim:.4f}</div><div class="lbl">Mean Semantic Sim</div></div>
</div>

<div class="pass-rate-bar"><div class="pass-rate-fill" style="width:{total_pass/n*100:.1f}%"></div></div>

<!-- ── PASS/FAIL THRESHOLDS ── -->
<h2>Evaluation Criteria</h2>
<table style="max-width:500px">
  <thead><tr><th>Criterion</th><th>Threshold</th><th>Metric</th></tr></thead>
  <tbody>
    <tr><td>Retrieval hit</td><td>RR ≥ {RR_PASS}</td><td>Reciprocal Rank (top-3 = 0.33)</td></tr>
    <tr><td>Answer quality</td><td>Cosine sim ≥ {SIM_PASS}</td><td>BAAI/bge-large-en-v1.5 embeddings</td></tr>
    <tr><td><strong>PASS</strong></td><td colspan="2">Both criteria met</td></tr>
    <tr><td><strong>NO-HIT</strong></td><td colspan="2">Retrieval miss only</td></tr>
    <tr><td><strong>LOW-SIM</strong></td><td colspan="2">Answer quality miss only</td></tr>
    <tr><td><strong>FAIL</strong></td><td colspan="2">Both criteria missed</td></tr>
  </tbody>
</table>

<!-- ── PER-NATURE BREAKDOWN ── -->
<h2>Per-Nature Breakdown</h2>
<div class="summary-nat">
<table>
  <thead><tr><th>Nature</th><th>Count</th><th>MRR</th><th>Mean Sim</th><th>Pass</th><th>Fail/Partial</th><th>Pass Rate</th></tr></thead>
  <tbody>{nature_rows}</tbody>
</table>
</div>

<!-- ── SYSTEM CONFIGURATION ── -->
<h2>System Configuration</h2>
<table style="max-width:700px">
  <thead><tr><th>Component</th><th>Setting</th></tr></thead>
  <tbody>
    <tr><td>LLM</td><td>Qwen/Qwen2.5-7B-Instruct — INT8 via OpenVINO GenAI on Intel iGPU</td></tr>
    <tr><td>Embedding Model</td><td>BAAI/bge-large-en-v1.5 on CPU (normalized)</td></tr>
    <tr><td>Vector DB</td><td>ChromaDB — collection: smart-kiosk-assistant-bge-large — 100 chunks</td></tr>
    <tr><td>Chunking</td><td>Semantic chunker — 5000-token passage windows, 300-token overlap, ≤1500 char chunks</td></tr>
    <tr><td>Retrieval top_k / fetch_k</td><td>3 / 6</td></tr>
    <tr><td>Max context chars</td><td>8000</td></tr>
    <tr><td>Max answer tokens</td><td>192</td></tr>
    <tr><td>GPU recycle every N calls</td><td>15</td></tr>
    <tr><td>Temperature</td><td>0.0 (deterministic)</td></tr>
    <tr><td>Knowledge base</td><td>store_knowledge_base.md — 120,123 chars</td></tr>
    <tr><td>Evaluation set</td><td>store_qna.jsonl — 1684 Q&amp;A pairs</td></tr>
  </tbody>
</table>
<h2>Raw config.yaml</h2>
{build_config_html()}

<!-- ── QUESTION TABLE ── -->
<h2>All Questions &amp; Answers</h2>
<div class="filters">
  <input id="searchInput" type="text" placeholder="Search question / answer…" oninput="filterTable()">
  <select id="natureFilter" onchange="filterTable()">
    <option value="">All natures</option>
    <option value="direct_fact">direct_fact</option>
    <option value="temporal">temporal</option>
    <option value="spanning">spanning</option>
  </select>
  <select id="verdictFilter" onchange="filterTable()">
    <option value="">All verdicts</option>
    <option value="PASS">PASS</option>
    <option value="FAIL">FAIL</option>
    <option value="NO-HIT">NO-HIT</option>
    <option value="LOW-SIM">LOW-SIM</option>
  </select>
  <span id="rowCount" style="color:#64748b;font-size:.8rem"></span>
</div>
<div class="tbl-scroll">
<table id="qTable">
  <thead>
    <tr>
      <th>ID</th><th>Nature</th><th>Question</th><th>Reference Answer</th>
      <th>LLM Answer</th><th>Retrieval RR</th><th>Semantic Sim</th><th>Time</th><th>Verdict</th>
    </tr>
  </thead>
  <tbody id="qTbody">
{q_rows}
  </tbody>
</table>
</div>

</div><!-- .page -->

<script>
function filterTable(){{
  var search  = document.getElementById('searchInput').value.toLowerCase();
  var nature  = document.getElementById('natureFilter').value.toLowerCase();
  var verdict = document.getElementById('verdictFilter').value.toUpperCase();
  var rows    = document.getElementById('qTbody').rows;
  var visible = 0;
  for(var i=0;i<rows.length;i++){{
    var row = rows[i];
    var text    = row.innerText.toLowerCase();
    var natCell = row.cells[1].innerText.toLowerCase();
    var vCell   = row.cells[8].innerText.toUpperCase().trim();
    var show = true;
    if(search  && !text.includes(search))    show=false;
    if(nature  && !natCell.includes(nature)) show=false;
    if(verdict && vCell!==verdict)           show=false;
    row.style.display = show ? '' : 'none';
    if(show) visible++;
  }}
  document.getElementById('rowCount').innerText = visible + ' of {n} rows shown';
}}
filterTable();
</script>
</body>
</html>"""
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"\nReport written → {out_path}")
    print(f"  Total: {n} | PASS: {total_pass} ({total_pass/n*100:.1f}%) | FAIL: {total_fail}")
    print(f"  MRR={mrr:.4f}  Hit@1={hit1:.4f}  Hit@3={hit3:.4f}  MeanSim={mean_sim:.4f}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", default=os.path.join(
        os.path.dirname(SERVICE_DIR), "knowledge-base", "store_qna.eval_checkpoint.jsonl"))
    parser.add_argument("--output", default=os.path.join(
        os.path.dirname(SERVICE_DIR), "knowledge-base", "eval_report.html"))
    args = parser.parse_args()

    print(f"Loading checkpoint: {args.checkpoint}")
    records = [json.loads(l) for l in open(args.checkpoint)]
    print(f"  {len(records)} records loaded.")

    sims = compute_sims(records)
    build_html(records, sims, args.output)


if __name__ == "__main__":
    main()
