from __future__ import annotations

import html
import json
from typing import Any


def render_blind_console(bundle: dict[str, Any], state: dict[str, Any], events: list[dict[str, Any]]) -> str:
    actions = "".join(
        f"<article class='action'><h3>{html.escape(a['name'])}</h3><code>{html.escape(a['id'])}</code><p>{html.escape(a['description'])}</p></article>"
        for a in bundle["available_actions"]
    )
    event_rows = "".join(
        f"<tr><td>{e['turn']}</td><td>{html.escape(e['action_name'])}</td><td>{html.escape(e['observation']['outcome_class'])}</td>"
        f"<td>{e['evidence_stage_after']}</td><td><code>{e['event_hash'][:14]}…</code></td></tr>"
        for e in events[-12:]
    ) or "<tr><td colspan='5'>No observations resolved yet.</td></tr>"
    ladder = "".join(
        f"<li class={'active' if row['stage'] == state['evidence_stage'] else ''}><strong>{row['stage']} · {html.escape(row['name'])}</strong><span>{html.escape(row['claim_ceiling'])}</span></li>"
        for row in bundle["evidence_ladder"]
    )
    payload = json.dumps({"bundle": bundle, "state": state, "events": events}, ensure_ascii=False).replace("</", "<\\/")
    return f"""<!doctype html>
<html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>AXM Blind Expedition Console</title>
<style>
:root {{ color-scheme: dark; --bg:#071015; --panel:#0e1b22; --line:#2a4c58; --text:#edf8f7; --muted:#9db6b9; --accent:#7de3d2; }}
* {{ box-sizing:border-box }} body {{ margin:0; font-family:system-ui,sans-serif; background:radial-gradient(circle at 50% 0,#17313a,var(--bg) 42%); color:var(--text) }}
main {{ max-width:1100px; margin:auto; padding:24px }} header {{ border-bottom:1px solid var(--line); padding-bottom:18px }}
h1 {{ margin:.2rem 0; font-size:clamp(1.7rem,4vw,3rem); letter-spacing:.08em }} .eyebrow {{ color:var(--accent); letter-spacing:.18em; text-transform:uppercase }}
.grid {{ display:grid; gap:16px; grid-template-columns:repeat(auto-fit,minmax(260px,1fr)); margin-top:18px }}
.panel,.action {{ background:rgba(14,27,34,.88); border:1px solid var(--line); border-radius:16px; padding:16px }}
.metric {{ font-size:2rem; color:var(--accent) }} code {{ color:#b8f5eb; overflow-wrap:anywhere }} p,span {{ color:var(--muted) }}
ul {{ list-style:none; padding:0 }} li {{ display:grid; gap:4px; border-left:3px solid var(--line); padding:10px 12px; margin:8px 0 }} li.active {{ border-left-color:var(--accent); background:#13292f }}
table {{ width:100%; border-collapse:collapse }} th,td {{ text-align:left; padding:10px; border-bottom:1px solid var(--line) }}
.actions {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(230px,1fr)); gap:12px }} .action h3 {{ margin-top:0 }}
.notice {{ padding:14px; border:1px dashed var(--accent); border-radius:12px; color:var(--muted) }}
</style></head><body><main>
<header><div class='eyebrow'>Blind player view · private scenario sealed</div><h1>{html.escape(bundle['system_name'])}</h1><p>{html.escape(bundle['mission'])}</p></header>
<section class='grid'>
<div class='panel'><div class='eyebrow'>Turn</div><div class='metric'>{state['turn']}</div><p>Status: {html.escape(state['status'])}</p></div>
<div class='panel'><div class='eyebrow'>Evidence stage</div><div class='metric'>{state['evidence_stage']}</div><p>{html.escape(state['claim_ceiling'])}</p></div>
<div class='panel'><div class='eyebrow'>Knowledge</div><div class='metric'>{state['knowledge_points']:.1f}</div><p>Mission time: {state['mission_time_hours']:.1f} h</p></div>
<div class='panel'><div class='eyebrow'>Pre-play commitment</div><code>{bundle['private_scenario_commitment_sha256']}</code></div>
</section>
<section class='grid'><div class='panel'><h2>Evidence ladder</h2><ul>{ladder}</ul></div>
<div class='panel'><h2>Blindness contract</h2><p>The exploring AI receives this public bundle and observations only. It does not receive the selected theory pair, origin class, hidden traits, or resolution secret.</p><div class='notice'>A later reveal can prove that the private scenario existed before play and that recorded events were not rewritten afterward.</div></div></section>
<section><h2>Available commands</h2><div class='actions'>{actions}</div></section>
<section class='panel'><h2>Observation ledger</h2><table><thead><tr><th>Turn</th><th>Action</th><th>Result</th><th>Stage</th><th>Hash</th></tr></thead><tbody>{event_rows}</tbody></table></section>
<script type='application/json' id='axm-public-state'>{payload}</script>
</main></body></html>"""
