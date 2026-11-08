# Agent Risk Atlas

How research with AI agents goes wrong: who fails, at which step, and what protects you.

**[Open the atlas](https://michalie.github.io/agent-risk-atlas/)** · [Swiss cheese slide](https://michalie.github.io/agent-risk-atlas/cheese.html)

![The atlas wall](docs/preview.png)

I made this for an ELIXIR hands-on training session on AI agents in life-science research. It fits on one screen, so you can project it during a discussion, and it works as a web page afterwards.

## What's on it

Each box is a risk. The rows say who fails: the agent, the checks around it, you in the moment, you over time, your team and field, and data governance. The columns follow the steps of a research project, from searching the literature to handing the work on.

Click a risk to see what protects against it and an example of what you could ask your agent. For some risks you also see the human failure that often lets the agent's error through.

The defences come in three groups:

- **The agent checks:** things you can ask the agent to run and show you.
- **You think first:** thinking only you can do, before the agent shows its version.
- **People and rules:** colleagues, experts, lab rules and settings.

The example requests are in plain words, so adapt them to your own work. The defences and the examples are my working practice. None of them has been tested in a study.

## Using it

Click a risk or a defence to highlight it. Esc or a click on empty space clears it, and the arrow keys move from risk to risk. You can link straight to one risk, for example [#B5](https://michalie.github.io/agent-risk-atlas/#B5).

The Swiss cheese slide takes four example errors and shows where each one is stopped as you switch the groups of defences on, one at a time.

## Sources

When you click a risk, its description shows numbered references to the list under the wall. Each reference is marked as a published source, my own observation, or my proposal. The published sources were checked against Crossref, arXiv or the publisher in November 2026.

It is my working map and not an official ELIXIR document. It deals with honest mistakes; misconduct is out of scope.

## How it was made

Drafted with AI agents (Claude, by Anthropic), then checked and edited by me. Three of the cited works have authors at Anthropic: the study on analysts following an agent's suggestions (F1), the study on skill formation (G2) and ImpossibleBench (C6).

## Changing it

The content is in `data/` as plain YAML files. `build.py` checks them and writes the two pages into `docs/`:

```
pip install -r requirements.txt
python3 build.py
```

Risk IDs stay fixed from version 1.0. If a risk is removed, its ID is not reused.

## Citing

Liegertová M. *Agent Risk Atlas*, version 1.0. 2026. https://github.com/MichaLie/agent-risk-atlas

## Licence

Text and data: CC BY 4.0 (see `LICENSE-content.md`). Code: MIT (see `LICENSE`).
