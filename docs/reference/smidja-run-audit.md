# Smidja run audit — 2026-11-21

This audit ran one small real task end to end on one machine, through both runtimes, and records every fault met on the way.

## What was run

The task was "read `README.md` and name its one heading", sent to the `scout` chain in a throwaway git project. The trace was kept in a temporary folder so no real run was touched. The model was a small hosted one, chosen from the machine's catalog.

| Run | Runtime | Result |
|---|---|---|
| first | internal | failed in the planner, see fault 2 |
| second | internal | success, summary names the heading |
| third | herdr | success, same summary, the agent seated in its own pane |

## Faults found

| # | Fault | Where | State |
|---|---|---|---|
| 1 | An agent with no `model:` of its own got the hoard's default (empty on a plain install) instead of `SMIDJA_LOCAL_MODEL`, so `builder` failed config validation with "no model" even though the environment named one. | `engine/smidja_modules/agents.py`, `_fill_models_from_hoard` | Fixed, test `TestModelInheritance` |
| 2 | A model refusal (here a 429 usage limit) surfaced as "no JSON object found in the response". The real cause sat in the raw stream. | `engine/smidja_modules/agent_pi.py`, `run` | Fixed: the error text is now raised |
| 3 | Asking for a run's state before its first trace row existed answered "no trace … no run has been recorded", which hides that the run was launched and may have died at start. | `runner/smidja_runner/verbs.py` | Fixed: `status` shows `not-traced-yet` and the launch log |
| 4 | There was no short way to start a run. The long form needs a chain name and a hand-written `Done means:` line, and there was no `status` verb. | `runner/smidja_runner/cli.py` | Added `run --task`, `--team`, `--project`, `status` |
| 5 | Ten tests under `tests/` fail on a clean checkout. Four look for `smidja_record.py` at the pre-split path, six need `rich` in the system Python, and `test_resume` does not import. | `tests/` | Open, issue filed |
| 6 | `--team <name>` is passed to the engine without checking that the config has such a team. A misspelt team is accepted at launch. | `runner/smidja_runner/verbs.py`, `run` | Open, issue filed |
| 7 | `smidja doctor` reports `prompts: fail` on a fresh install until `smidja up` is run. Whether `run` stamps them by itself was not tested. | `runner/smidja_runner/verbs.py` | Open, issue filed |
| 8 | Under the herdr runtime, `stop` signals the pane's shell, not the agent inside it. Whether the agent then ends was not tested. | `engine/smidja_modules/herdr_seat.py` | Open, issue filed |

## Two notes for the host

The host's pi extensions inject a session-start digest into every agent the smithy starts. That is the host's own configuration, not the smithy's, and it adds tokens to each turn. It is recorded here so the host can decide.

The default chain, `plan-build-test`, is heavier than a read-only question needs. A phone user can name a lighter chain with `SMIDJA_DEFAULT_CHAIN`.

## The herdr runtime, as tested

The seat was proved two ways. Unit tests drive it against a stand-in `herdr` script: one workspace per run, a new pane per turn, the exit code read back, a failed turn keeps its pane. A live run then seated a real turn in a real herdr workspace and the engine read its result back through the same event stream.
