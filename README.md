# Smíðja — the smithy

**The agent factory.** Smíðja seats a roster of agents, runs them through a chain
of phases, keeps every run as a trace you can read afterwards, and shows the whole
thing on a board at `:8437`.

It is the forge Ymir's workers are made in: where a team is composed, a model is
chosen per seat, an instruction is written once and dispatched, and where the
result is inspected rather than assumed.

> Load `SKILL.md` when working *on* the smithy. This file is for standing it up.

## Install

```bash
npm install -g @zerwiz/smidja
```

That installs the factory: the skill, the smithy's own skills, the templates, the
cookbooks and references, the Python scripts, and the visualizer's **source**.
There is no CLI entry point yet — the visualizer is the door, and it runs on
`bun`, which Ymir's install already provides:

```bash
cd "$(npm root -g)/@zerwiz/smidja"
bun --cwd apps/visualizer install
bun --cwd apps/visualizer run build     # the UI (./dist), which the API serves
bun --cwd apps/visualizer run server    # :8437
```

Or work from a checkout, which is the same tree:

```bash
git clone https://github.com/zerwiz/smidja.git && cd smidja
```

`bun` runs the visualizer; `python3` is needed by the factory's own scripts
(`scripts/install.py`, `make_config.py`, `make_smidja.py`).

## Run the visualizer

```bash
bun --cwd apps/visualizer run server                     # :8437, reads ./smidja/smidja_data/smidja.db
bun --cwd apps/visualizer run server --db /path/to/smidja.db
CMD_DB=/path/to/smidja.db PORT=8437 bun --cwd apps/visualizer run server
```

The API is a read-only JSON face over a target repository's `smidja.db`, plus the
built UI when `dist/` exists. There is **no ingest endpoint and no websocket** —
the path is agents → sqlite → the UI, and the UI gets there by polling. The single
write is archiving a session (one review flag on one row).

Useful targets: `dev` (Vite), `dev:all` (server and Vite together), `build`
(`vue-tsc` then Vite), `typecheck`, `lint`.

## What is in here

```
layout[7]{path,holds}:
  "SKILL.md","the skill: load it before changing factory behaviour"
  "skills/","the smithy's own skills — how to start it, brief it, run a team, and edit the roster"
  "templates/","what a new smithy is stamped from: smidja, smidja.config.yaml, harness and prompt engineering, env.sample, justfile"
  "cookbooks/","task-shaped guides: overview · install · create/update config · create/update smidja · run · prompt · modules"
  "references/","config · handoff · observability"
  "scripts/","install.py · make_config.py · make_smidja.py"
  "apps/visualizer/","the board: a Bun server over the run database, a Vue UI, and the shared types between them"
```

### The skills it ships with

`smidja-start` (pick a team and models) · `smidja-launcher` (converge the
environment, run a chain, watch, audit, stop) · `smidja-instructions` (turn a
vague ask into an instruction the smithy can execute) · `how-to-run-agent-teams` ·
`create-new-agent` · `create-new-teams` · `add-or-edit-ai-models` · `volundr` (the
orchestrator's own way of working) · `git-ops` (branches, gated commits, sync).

## The shape of a run

```
roster (agents + a model per seat)
   └── chain (phases: scout · plan · build · review)
         └── envelopes (what each phase is allowed to read and write)
               └── trace (one row per turn, in smidja.db)
                     └── the board on :8437
```

**Kaia** orchestrates — she recalls from the memory well before a dispatch and
writes back after it — and **Völundr** is the master craftsman's way of working:
coordinate the work, dispatch the seats, verify what comes back.

## Licence and notice

Apache-2.0 — see [`LICENSE`](LICENSE) and [`NOTICE`](NOTICE).
