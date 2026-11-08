"""Build the Agent Risk Atlas from the data files.

What it does: reads data/meta.yaml, risks.yaml, defences.yaml, references.yaml and paths.yaml, runs plain
checks (every problem is listed with its file, record and field), numbers the references in order of first
use, and writes two self-contained pages into docs/ (served by GitHub Pages):
  docs/index.html   the wall: one 16:9 screen, click a risk to spotlight its twin and defences
  docs/cheese.html  the Swiss cheese slide: four illustrative paths, defences switched on step by step
Why: one source of truth, so the wall, the slide and the reference list cannot drift apart.
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

layer_who = {"origin": {"agent"}, "checks": {"checks"}, "you": {"you-now", "you-time"}, "team": {"team"}}
for i, p in enumerate(paths):
    for layer, allowed in layer_who.items():
        rid = p.get(layer)
        if rid not in by_id:
            err(f"paths.yaml '{p.get('name', i + 1)}': {layer} '{rid}' is not a risk id")
        elif by_id[rid]["who"] not in allowed:
            err(f"paths.yaml '{p.get('name', i + 1)}': {layer} '{rid}' is in the wrong layer")

# number references in order of first use
order = []
for r in risks:
    for k in r.get("refs") or []:
        if k in refs and k not in order:
            order.append(k)
extra = ["fei2026", "reason2000"]   # cited in the About text and on the Swiss cheese slide
for k in extra:
    if k in refs and k not in order:
        order.append(k)
for k in refs:
    if k not in order:
        warn(f"references.yaml '{k}': not cited anywhere")
num = {k: i + 1 for i, k in enumerate(order)}

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


def page(template_name, out_name):
    t = (HERE / "templates" / template_name).read_text(encoding="utf-8")
    if t.count("/*__DATA__*/null") != 1:
        sys.exit(f"templates/{template_name}: the data placeholder must appear exactly once")
    body = t.replace("/*__DATA__*/null", embed(data))
    doc = ("<!doctype html>\n<html lang=\"en\">\n<meta charset=\"utf-8\">\n"
           "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
           "<meta name=\"description\" content=\"How research with AI agents goes wrong, who fails, and what protects you.\">\n"
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
page("cheese.html", "cheese.html")
for w in warnings:
    print("warning:", w)
n_twin = sum(1 for r in risks if r["twin"])
print(f"ok: {len(risks)} risks, {len(defences)} defences, {len(reflist)} references, {n_twin} twin pairs, "
      f"{len(paths)} paths -> docs/index.html, docs/cheese.html")
