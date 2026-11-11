"""Build the Agent Risk Atlas from the data files.

What it does: reads data/meta.yaml, risks.yaml, defences.yaml, references.yaml and paths.yaml, runs plain
checks (every problem is listed with its file, record and field), numbers the references in order of first
use, and writes self-contained pages into docs/ (served by GitHub Pages):
  docs/index.html   the wall: one 16:9 screen, click a risk to spotlight its twin and defences
  docs/paths.html   companion chains: 7 paper error paths + 5 deskilling tracks, defences switched on step by step
  docs/essay.html   introductory narrative essay for researchers and PhD students, wired to the same data
  docs/cheese.html  redirect stub to paths.html so existing links and bookmarks keep working
Why: one source of truth, so the wall, the companion views and the reference list cannot drift apart.
Rerun: python3 build.py   (needs PyYAML; see requirements.txt)
"""
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
D = HERE / "data"


def load(name):
    return yaml.safe_load((D / name).read_text(encoding="utf-8"))


meta, risks, defences = load("meta.yaml"), load("risks.yaml"), load("defences.yaml")
refs, paths = load("references.yaml"), load("paths.yaml")

errors, warnings = [], []
err = errors.append
warn = warnings.append

type_to_who = {t: w["id"] for w in meta["who"] for t in w["types"]}
for k, v in meta["kinds"].items():
    if not isinstance(v, dict) or not v.get("name") or not v.get("says"):
        err(f"meta.yaml kinds '{k}': needs a name and a says line")
stage_ids = [s["id"] for s in meta["stages"]]
def_by_id = {}
for i, d in enumerate(defences):
    where = f"defences.yaml #{i + 1}"
    for f in ("id", "kind", "name", "does"):
        if not d.get(f):
            err(f"{where}: missing '{f}'")
    if d.get("kind") not in meta["kinds"]:
        err(f"{where} ({d.get('id')}): kind must be one of {list(meta['kinds'])}")
    if d.get("id") in def_by_id:
        err(f"{where}: duplicate defence id '{d['id']}'")
    if bool(d.get("example")) == bool(d.get("no_example")):
        err(f"{where} ({d.get('id')}): give either an example instruction or a no_example reason")
    if len(str(d.get("example", ""))) > 240:
        warn(f"{where} ({d.get('id')}): example is {len(d['example'])} characters; keep it under 240 for the caption")
    def_by_id[d.get("id")] = d

for k, r in refs.items():
    if r.get("kind") not in ("source", "observation", "proposal"):
        err(f"references.yaml '{k}': kind must be source, observation or proposal")
    if not r.get("text"):
        err(f"references.yaml '{k}': missing 'text'")
    if r.get("kind") == "source" and not str(r.get("url", "")).startswith("https://"):
        err(f"references.yaml '{k}': a source needs an https url")

seen = set()
by_id = {}
for i, r in enumerate(risks):
    rid = r.get("id", f"#{i + 1}")
    where = f"risks.yaml {rid}"
    for f in ("id", "name", "type", "stage", "looks_like", "refs"):
        if not r.get(f):
            err(f"{where}: missing '{f}'")
    if "defences" not in r:
        err(f"{where}: missing 'defences' (use [] together with open: true)")
    if not re.fullmatch(r"[A-I]\d+", str(rid)):
        err(f"{where}: id must be a letter A–I followed by a number")
    elif r.get("type") and str(rid)[0] != r["type"]:
        err(f"{where}: id letter does not match type '{r.get('type')}'")
    if rid in seen:
        err(f"{where}: duplicate id")
    seen.add(rid)
    by_id[rid] = r
    if r.get("type") not in type_to_who:
        err(f"{where}: unknown type '{r.get('type')}'")
    if r.get("stage") not in stage_ids:
        err(f"{where}: unknown stage '{r.get('stage')}' (use one of {stage_ids})")
    for k in r.get("refs") or []:
        if k not in refs:
            err(f"{where}: unknown reference '{k}'")
    for d in r.get("defences") or []:
        if d not in def_by_id:
            err(f"{where}: unknown defence '{d}'")
    if "open" in r and not isinstance(r["open"], bool):
        err(f"{where}: open must be true or false")
    if not r.get("defences") and not r.get("open"):
        err(f"{where}: no defences; add one or set open: true")
    if r.get("example_from"):
        src = def_by_id.get(r["example_from"])
        if not src or not src.get("example"):
            err(f"{where}: example_from '{r['example_from']}' is not a defence with an example")
        elif r.get("example"):
            err(f"{where}: give example or example_from, not both")
        else:
            r["example"] = src["example"]   # the risk shows its defence's text word for word
    if not r.get("open") and bool(r.get("example")) == bool(r.get("no_example")):
        err(f"{where}: give either an example instruction or a no_example reason")
    if len(str(r.get("example", ""))) > 150:
        warn(f"{where}: example is {len(r['example'])} characters; keep it under 150 so it fits two lines in the caption")
    if len(str(r.get("name", ""))) > 30:
        warn(f"{where}: name is {len(r['name'])} characters; keep it under 30 for the wall")
    if len(str(r.get("looks_like", ""))) > 170:
        warn(f"{where}: looks_like is {len(r['looks_like'])} characters; keep it under 170")
    r["who"] = type_to_who.get(r.get("type"))
    r.setdefault("open", False)
    r.setdefault("twin", None)

agent_side = {"agent", "checks"}
for r in risks:
    t = r.get("twin")
    if t:
        if t not in by_id:
            err(f"risks.yaml {r['id']}: twin '{t}' does not exist")
        elif t == r["id"]:
            err(f"risks.yaml {r['id']}: a risk cannot be its own twin")
        elif r["who"] not in agent_side or by_id[t]["who"] in agent_side:
            err(f"risks.yaml {r['id']}: a twin goes from an agent or check risk to a human or team risk")

used_defs = {d for r in risks for d in r.get("defences") or []}
for d in def_by_id:
    if d not in used_defs:
        err(f"defences.yaml '{d}': no risk uses this defence")
for w in meta["who"]:
    if not any(r["who"] == w["id"] for r in risks):
        warn(f"meta.yaml: row '{w['label']}' has no risks")

def check_risk_list(where, rids):
    if not isinstance(rids, list) or not rids:
        err(f"{where}: needs a non-empty list of risk ids")
        return
    for rid in rids:
        if rid not in by_id:
            err(f"{where}: unknown risk '{rid}'")


def check_catch_box(where, box):
    if not isinstance(box, dict):
        err(f"{where}: must be a mapping")
        return
    k = box.get("kind")
    if k not in meta["kinds"]:
        err(f"{where}: kind '{k}' must be one of {list(meta['kinds'])}")
    defs = box.get("defences")
    if not isinstance(defs, list) or not defs:
        err(f"{where}: needs a non-empty list of defences")
    else:
        for d in defs:
            if d not in def_by_id:
                err(f"{where}: unknown defence '{d}'")
            elif k in meta["kinds"] and def_by_id[d]["kind"] != k:
                err(f"{where}: defence '{d}' is kind '{def_by_id[d]['kind']}', expected '{k}'")
    if not box.get("how"):
        err(f"{where}: missing 'how'")


if not isinstance(paths, dict) or not paths.get("paper") or not paths.get("deskill"):
    err("paths.yaml: needs 'paper' and 'deskill' lists")
else:
    seen_p = set()
    for i, p in enumerate(paths["paper"]):
        pid = p.get("id", f"#{i + 1}")
        where = f"paths.yaml paper '{pid}'"
        for f in ("id", "name", "tag"):
            if not p.get(f):
                err(f"{where}: missing '{f}'")
        if pid in seen_p:
            err(f"{where}: duplicate id")
        seen_p.add(pid)
        orig = p.get("origin") or {}
        check_risk_list(f"{where} origin", orig.get("risks"))
        for f in ("title", "text"):
            if not orig.get(f):
                err(f"{where} origin: missing '{f}'")
        gates = p.get("gates") or []
        if [g.get("layer") for g in gates] != ["checks", "you", "team"]:
            err(f"{where}: gates must be in order ['checks', 'you', 'team']")
        for g in gates:
            gw = f"{where} gate '{g.get('layer')}'"
            check_risk_list(gw, g.get("risks"))
            for f in ("open_title", "open_text"):
                if not g.get(f):
                    err(f"{gw}: missing '{f}'")
            if "catch" in g:
                check_catch_box(f"{gw} catch", g["catch"])
        rev = p.get("review") or {}
        for f in ("open_title", "open_text", "why_passes"):
            if not rev.get(f):
                err(f"{where} review: missing '{f}'")
        claim = p.get("paper_claim") or {}
        for f in ("bad", "saved"):
            if not claim.get(f):
                err(f"{where} paper_claim: missing '{f}'")

    seen_d = set()
    for i, t in enumerate(paths["deskill"]):
        tid = t.get("id", f"#{i + 1}")
        where = f"paths.yaml deskill '{tid}'"
        for f in ("id", "name", "slide8"):
            if not t.get(f):
                err(f"{where}: missing '{f}'")
        if tid in seen_d:
            err(f"{where}: duplicate id")
        seen_d.add(tid)
        sc = t.get("shortcut") or {}
        for f in ("title", "text"):
            if not sc.get(f):
                err(f"{where} shortcut: missing '{f}'")
        ct = t.get("checks_trap") or {}
        check_risk_list(f"{where} checks_trap", ct.get("risks"))
        for f in ("title", "text"):
            if not ct.get(f):
                err(f"{where} checks_trap: missing '{f}'")
        cm = t.get("comfort") or {}
        check_risk_list(f"{where} comfort", cm.get("risks"))
        for f in ("open_title", "open_text"):
            if not cm.get(f):
                err(f"{where} comfort: missing '{f}'")
        if "break_here" in cm:
            check_catch_box(f"{where} comfort break_here", cm["break_here"])
        er = t.get("erosion") or {}
        check_risk_list(f"{where} erosion", er.get("risks"))
        for f in ("open_title", "open_text"):
            if not er.get(f):
                err(f"{where} erosion: missing '{f}'")
        if "break_here" in er:
            check_catch_box(f"{where} erosion break_here", er["break_here"])
        if "break_here" not in cm and "break_here" not in er:
            err(f"{where}: needs break_here on comfort or erosion")
        cr = t.get("crunch") or {}
        check_risk_list(f"{where} crunch", cr.get("risks"))
        for f in ("bad", "saved"):
            if not cr.get(f):
                err(f"{where} crunch: missing '{f}'")

# number references in order of first use
order = []
for r in risks:
    for k in r.get("refs") or []:
        if k in refs and k not in order:
            order.append(k)
extra = ["fei2026", "reason2000", "nusrat2025", "bucinca2021", "vasconcelos2023"]   # cited in the About text, on paths.html, or only in the essay
for k in extra:
    if k in refs and k not in order:
        order.append(k)
for k in refs:
    if k not in order:
        warn(f"references.yaml '{k}': not cited anywhere")
num = {k: i + 1 for i, k in enumerate(order)}

# verify citation keys in templates/essay.html so essay footnotes never drift from references.yaml
essay_tpl = (HERE / "templates" / "essay.html").read_text(encoding="utf-8")
for raw in re.findall(r'data-cite="([^"]+)"', essay_tpl):
    for k in (s.strip() for s in raw.split(",") if s.strip()):
        if k not in refs:
            err(f"templates/essay.html: unknown data-cite reference '{k}'")

if errors:
    print("The data has problems; nothing was written:\n  " + "\n  ".join(errors))
    sys.exit(1)

for r in risks:
    r["refnums"] = [num[k] for k in r["refs"]]
reflist = [{"n": num[k], "key": k, **refs[k]} for k in order]
data = {"meta": meta, "risks": risks, "defences": defences, "refs": reflist, "paths": paths,
        "cite": {k: num[k] for k in extra}}


def embed(obj):
    s = json.dumps(obj, ensure_ascii=False)
    return s.replace("<", "\\u003c").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")


SITE = "https://michalie.github.io/agent-risk-atlas/"


OG_META = {
    "index.html": (
        "Agent Risk Atlas",
        "How research with AI agents goes wrong, who fails, and what protects you.",
    ),
    "paths.html": (
        "Into the paper & into deskilling · Research with AI agents",
        "Seven ways plausible errors reach print and five ways passive oversight erodes research judgement.",
    ),
    "essay.html": (
        "The Quiet Errors Inside Good-Looking Science · Agent Risk Atlas",
        "How AI agents slip plausible mistakes past smart researchers, how passive oversight deskills labs, and five habits that stop both.",
    ),
}


def page(template_name, out_name):
    t = (HERE / "templates" / template_name).read_text(encoding="utf-8")
    if t.count("/*__DATA__*/null") != 1:
        sys.exit(f"templates/{template_name}: the data placeholder must appear exactly once")
    body = t.replace("/*__DATA__*/null", embed(data))
    og_title, og_desc = OG_META.get(out_name, OG_META["index.html"])
    doc = ("<!doctype html>\n<html lang=\"en\">\n<meta charset=\"utf-8\">\n"
           "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
           f"<meta name=\"description\" content=\"{og_desc}\">\n"
           # link previews (chat, email, social): title, line and the wall image when someone pastes the address
           "<meta property=\"og:type\" content=\"website\">\n"
           f"<meta property=\"og:url\" content=\"{SITE}{'' if out_name == 'index.html' else out_name}\">\n"
           f"<meta property=\"og:title\" content=\"{og_title}\">\n"
           f"<meta property=\"og:description\" content=\"{og_desc}\">\n"
           f"<meta property=\"og:image\" content=\"{SITE}preview.png\">\n"
           "<meta name=\"twitter:card\" content=\"summary_large_image\">\n"
           + body + "\n</html>\n")
    (HERE / "docs").mkdir(exist_ok=True)
    (HERE / "docs" / out_name).write_text(doc, encoding="utf-8")
    # if Node.js is installed, make sure the page script still parses (a stray quote in text breaks the whole page)
    if shutil.which("node"):
        script = doc.split("<script>")[1].split("</script>")[0]
        res = subprocess.run(["node", "-e", "new Function(require('fs').readFileSync(0, 'utf8'))"],
                             input=script, capture_output=True, text=True)
        if res.returncode != 0:
            sys.exit(f"docs/{out_name}: the page script does not parse:\n{res.stderr.strip().splitlines()[-1]}")


page("wall.html", "index.html")
page("paths.html", "paths.html")
page("essay.html", "essay.html")

redirect = (
    "<!doctype html>\n<html lang=\"en\">\n<meta charset=\"utf-8\">\n"
    "<title>Redirecting · Agent Risk Atlas</title>\n"
    f"<link rel=\"canonical\" href=\"{SITE}paths.html\">\n"
    "<meta http-equiv=\"refresh\" content=\"0; url=paths.html\">\n"
    "<script>location.replace('paths.html' + (location.hash || '#paper'));</script>\n"
    "<p style=\"font:16px system-ui,sans-serif;padding:24px\">Moved to "
    "<a href=\"paths.html\">How it happens · Agent Risk Atlas</a>.</p>\n</html>\n"
)
(HERE / "docs" / "cheese.html").write_text(redirect, encoding="utf-8")

for w in warnings:
    print("warning:", w)
n_twin = sum(1 for r in risks if r["twin"])
print(f"ok: {len(risks)} risks, {len(defences)} defences, {len(reflist)} references, {n_twin} twin pairs, "
      f"{len(paths['paper'])} paper paths + {len(paths['deskill'])} deskill tracks -> docs/index.html, docs/paths.html, docs/essay.html, docs/cheese.html")
