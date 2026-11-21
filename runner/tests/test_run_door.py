"""The run door: `run --task`, `status`, the runtime choice and the herdr seat road.

Fenced like test_runner.py (a temp trace, a temp HOME). herdr is a stand-in script, so
the herdr road is proved end to end without touching anyone's real workspaces.
"""

from __future__ import annotations

import json
import os
import stat
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_runner import Fenced, FACTORY  # noqa: E402

from smidja_runner import cli, verbs  # noqa: E402

FAKE_HERDR = textwrap.dedent("""\
    #!/usr/bin/env bash
    # a stand-in for herdr: records every call, "runs" a pane by running its command
    echo "$@" >> "$FAKE_HERDR_LOG"
    case "$1 $2" in
      "workspace list")   echo '{"result":{"workspaces":[]}}' ;;
      "workspace create") echo '{"result":{"workspace_id":"w9","pane_id":"w9:p1"}}' ;;
      "pane split")       echo '{"result":{"pane_id":"w9:p2"}}' ;;
      "pane run")         shift 3; bash -c "$*" >/dev/null 2>&1 ;;
      "pane process-info") echo '{"result":{"pid":4242}}' ;;
      *) echo '{}' ;;
    esac
""")


class TestRuntimeChoice(Fenced):
    def test_the_default_runtime_is_internal(self):
        os.environ.pop("SMIDJA_AGENT_RUNTIME", None)
        code, out = cli.execute(["run", "scout", "x.\nDone means: y.", "--dry-run"])
        self.assertEqual(code, 0, out)
        self.assertEqual(out["runtime"], "internal")

    def test_the_environment_sets_the_default_and_the_flag_overrides_it(self):
        os.environ["SMIDJA_AGENT_RUNTIME"] = "herdr"
        try:
            code, out = cli.execute(["run", "scout", "x.\nDone means: y.", "--dry-run"])
            self.assertEqual(out["runtime"], "herdr")
            code, out = cli.execute(["run", "scout", "x.\nDone means: y.", "--dry-run", "--runtime", "internal"])
            self.assertEqual(out["runtime"], "internal")
        finally:
            os.environ.pop("SMIDJA_AGENT_RUNTIME")

    def test_an_unknown_runtime_is_refused_by_name(self):
        os.environ["SMIDJA_AGENT_RUNTIME"] = "docker"
        try:
            code, out = cli.execute(["run", "scout", "x.\nDone means: y.", "--dry-run"])
        finally:
            os.environ.pop("SMIDJA_AGENT_RUNTIME")
        self.assertEqual(code, 1)
        self.assertIn("unknown runtime", out["refused"])

    def test_herdr_asked_for_and_absent_is_a_refusal_not_a_silent_fallback(self):
        os.environ["SMIDJA_HERDR_BIN"] = "no-such-herdr-here"
        try:
            code, out = cli.execute(["run", "scout", "x.\nDone means: y.", "--runtime", "herdr"])
        finally:
            os.environ.pop("SMIDJA_HERDR_BIN")
        self.assertEqual(code, 1)
        self.assertIn("herdr runtime was asked for", out["refused"])



class TestTeamCheck(Fenced):
    """Run audit fault 6: a team the config does not define is refused at launch."""

    def _with_teams(self, names):
        real = verbs._block_list
        verbs._block_list = lambda w, key, book: ({"stacks": [{"name": n} for n in names]} if key == "stacks" else real(w, key, book))
        self.addCleanup(setattr, verbs, "_block_list", real)

    def test_a_misspelt_team_is_refused_with_the_list(self):
        self._with_teams(["local-cron", "local-agile"])
        code, out = cli.execute(["run", "scout", "x.\nDone means: y.", "--dry-run", "--team", "local-crn"])
        self.assertEqual(code, 1, out)
        self.assertIn("no team 'local-crn'", out["refused"])
        self.assertIn("local-cron", json.dumps(out))

    def test_a_known_team_is_accepted(self):
        self._with_teams(["local-cron"])
        code, out = cli.execute(["run", "scout", "x.\nDone means: y.", "--dry-run", "--team", "local-cron"])
        self.assertEqual(code, 0, out)
        self.assertEqual(out["team"], "local-cron")

    def test_no_stacks_block_leaves_the_engine_to_judge(self):
        self._with_teams([])
        code, out = cli.execute(["run", "scout", "x.\nDone means: y.", "--dry-run", "--team", "anything"])
        self.assertEqual(code, 0, out)



class TestRunStampsPrompts(Fenced):
    """Run audit fault 7: a run stamps the missing prompts itself, before it launches."""

    def test_the_run_stamps_before_it_launches(self):
        order = []
        real_stamp, real_popen = verbs.stamp_runtime, verbs.subprocess.Popen
        verbs.stamp_runtime = lambda w: order.append("stamp") or ["p1", "p2"]

        def no_launch(cmd, *a, **k):
            if "--smidja-id" not in list(cmd):          # a helper's own subprocess, not the launch
                return real_popen(cmd, *a, **k)
            order.append("launch")
            raise RuntimeError("stop here")
        verbs.subprocess.Popen = no_launch
        self.addCleanup(setattr, verbs, "stamp_runtime", real_stamp)
        self.addCleanup(setattr, verbs.subprocess, "Popen", real_popen)
        with self.assertRaises(RuntimeError):
            verbs.run(verbs.paths.where(), "scout", "x.\nDone means: y.")
        self.assertEqual(order, ["stamp", "launch"])

    def test_a_dry_run_stamps_nothing(self):
        called = []
        real = verbs.stamp_runtime
        verbs.stamp_runtime = lambda w: called.append(1) or []
        self.addCleanup(setattr, verbs, "stamp_runtime", real)
        code, out = cli.execute(["run", "scout", "x.\nDone means: y.", "--dry-run"])
        self.assertEqual(code, 0, out)
        self.assertEqual(called, [])



class TestHomeTeams(Fenced):
    """Teams live in the operator's home, so every machine has them (2026-11-21)."""

    def setUp(self):
        super().setUp()
        self.teams = Path(self.tmp.name) / "teams.yaml"
        os.environ["SMIDJA_TEAMS"] = str(self.teams)
        self.addCleanup(os.environ.pop, "SMIDJA_TEAMS", None)
        real = verbs.catalog_has
        verbs.catalog_has = lambda m: not str(m).startswith("absent/")
        self.addCleanup(setattr, verbs, "catalog_has", real)
        agents = [a.get("name") for a in verbs._config_blocks(verbs.paths.where()).get("agents") or []]
        self.agent = agents[0] if agents else "builder"

    def write(self, text):
        self.teams.write_text(textwrap.dedent(text))

    def test_a_home_team_is_listed(self):
        self.write(f"""\
            stacks:
              local-agile:
                description: the local team
                agents:
                  {self.agent}: local/model-a
            """)
        code, out = cli.execute(["team", "list"])
        self.assertEqual(code, 0, out)
        self.assertIn("local-agile", json.dumps(out))

    def test_the_first_model_this_machine_serves_is_used(self):
        self.write(f"""\
            stacks:
              local-agile:
                agents:
                  {self.agent}: [absent/big, local/model-b]
            """)
        code, out = cli.execute(["run", "scout", "x.\nDone means: y.", "--dry-run", "--team", "local-agile"])
        self.assertEqual(code, 0, out)
        self.assertEqual(out["team_models"], {self.agent: "local/model-b"})

    def test_a_team_with_no_servable_model_is_refused(self):
        self.write(f"""\
            stacks:
              t:
                agents:
                  {self.agent}: [absent/x]
            """)
        code, out = cli.execute(["run", "scout", "x.\nDone means: y.", "--dry-run", "--team", "t"])
        self.assertEqual(code, 1, out)
        self.assertIn("no model for agent", out["refused"])

    def test_an_unknown_agent_in_a_team_is_refused(self):
        self.write("""\
            stacks:
              t:
                agents:
                  nobody-here: local/x
            """)
        code, out = cli.execute(["run", "scout", "x.\nDone means: y.", "--dry-run", "--team", "t"])
        self.assertEqual(code, 1, out)
        self.assertIn("does not have", out["refused"])


class TestTaskForm(Fenced):
    def test_task_adds_a_done_line_and_uses_the_default_chain(self):
        os.environ["SMIDJA_DEFAULT_CHAIN"] = "scout"
        try:
            code, out = cli.execute(["run", "--task", "look at the README", "--team", "alpha", "--dry-run"])
        finally:
            os.environ.pop("SMIDJA_DEFAULT_CHAIN")
        self.assertEqual(code, 0, out)
        self.assertEqual(out["chain"], "smidja_scout")
        self.assertEqual(out["team"], "alpha")

    def test_a_named_chain_beside_task_is_the_chain(self):
        code, out = cli.execute(["run", "scout", "--task", "look", "--dry-run"])
        self.assertEqual(code, 0, out)
        self.assertEqual(out["chain"], "smidja_scout")

    def test_strict_mode_keeps_the_done_means_rule(self):
        os.environ["SMIDJA_STRICT_DONE"] = "1"
        try:
            code, out = cli.execute(["run", "--task", "look", "--dry-run"])
        finally:
            os.environ.pop("SMIDJA_STRICT_DONE")
        self.assertEqual(code, 1)
        self.assertIn("Done means", out["refused"])


class TestStatus(Fenced):
    def test_status_names_state_runtime_phase_and_link(self):
        self.add_run("s1", status="running", child=False)
        d = Path(os.environ["SMIDJA_DATA_DIR"]) / "sessions" / "s1"
        d.mkdir(parents=True)
        (d / "run.json").write_text(json.dumps({"runtime": "herdr", "team": "alpha"}))
        code, out = cli.execute(["status", "s1"])
        self.assertEqual(code, 0, out)
        self.assertEqual(out["runtime"], "herdr")
        self.assertEqual(out["team"], "alpha")
        self.assertEqual(out["state"], "running")
        self.assertTrue(out["viewer"].endswith("/#/sessions/s1"))

    def test_status_of_an_unknown_run_is_a_refusal(self):
        code, out = cli.execute(["status", "ghost"])
        self.assertEqual(code, 1)
        self.assertIn("no such run", out["refused"])

    def test_a_launched_run_with_no_trace_yet_shows_its_launch_log(self):
        d = Path(os.environ["SMIDJA_DATA_DIR"]) / "sessions" / "early"
        d.mkdir(parents=True)
        (d / "run.json").write_text(json.dumps({"runtime": "internal"}))
        (d / "launch.log").write_text("config validation failed: no model\n")
        code, out = cli.execute(["status", "early"])
        self.assertEqual(code, 0, out)
        self.assertEqual(out["state"], "not-traced-yet")
        self.assertIn("no model", out["launch_log"])


class TestHerdrSeat(Fenced):
    """The seat road, end to end, against a stand-in herdr."""

    def setUp(self):
        super().setUp()
        sys.path.insert(0, str(FACTORY / "engine"))
        from smidja_modules import herdr_seat
        self.seat_mod = herdr_seat
        herdr_seat._workspace.clear()
        root = Path(self.tmp.name)
        self.log = root / "herdr.log"
        fake = root / "herdr"
        fake.write_text(FAKE_HERDR)
        fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
        self.env_saved = {k: os.environ.get(k) for k in ("SMIDJA_HERDR_BIN", "FAKE_HERDR_LOG", "PATH")}
        os.environ.update({"SMIDJA_HERDR_BIN": str(fake), "FAKE_HERDR_LOG": str(self.log),
                           "SMIDJA_RUN_ID": "t1"})

    def tearDown(self):
        for k, v in self.env_saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        os.environ.pop("SMIDJA_RUN_ID", None)
        super().tearDown()

    def test_runtime_reads_the_environment(self):
        os.environ.pop("SMIDJA_AGENT_RUNTIME", None)
        self.assertEqual(self.seat_mod.runtime(), "internal")
        os.environ["SMIDJA_AGENT_RUNTIME"] = "herdr"
        try:
            self.assertEqual(self.seat_mod.runtime(), "herdr")
        finally:
            os.environ.pop("SMIDJA_AGENT_RUNTIME")

    def test_a_turn_is_seated_streamed_and_its_exit_code_read(self):
        raw = Path(self.tmp.name) / "turn" / "raw_output.jsonl"
        argv = ["bash", "-c", "echo '{\"type\":\"a\"}'; echo '{\"type\":\"b\"}'"]
        s = self.seat_mod.seat(argv, self.tmp.name, raw, {"SMIDJA_X": "1"}, "t1 · demo")
        lines = [json.loads(x)["type"] for x in s.lines()]
        self.assertEqual(lines, ["a", "b"])
        self.assertEqual(s.returncode, 0)
        calls = self.log.read_text()
        self.assertIn("workspace create --label smidja t1", calls)
        self.assertIn("pane run w9:p1", calls)

    def test_pid_is_the_agents_own_not_the_panes_shell(self):
        """Run audit fault 8: the stand-in herdr says the pane's pid is 4242; the seat
        must report the agent's own pid, which the agent itself prints."""
        raw = Path(self.tmp.name) / "turn-pid" / "raw_output.jsonl"
        s = self.seat_mod.seat(["bash", "-c", "echo \"{\\\"type\\\":\\\"$$\\\"}\""], self.tmp.name, raw, {}, "t1 · pid")
        pid = s.pid()
        lines = [json.loads(x)["type"] for x in s.lines()]
        self.assertNotEqual(pid, 4242)
        self.assertEqual(str(pid), lines[0])

    def test_a_seated_pane_is_recorded_and_closed_by_close_panes(self):
        seats = Path(self.tmp.name) / "seats"
        os.environ["SMIDJA_SEAT_DIR"] = str(seats)
        try:
            raw = Path(self.tmp.name) / "turn-close" / "raw_output.jsonl"
            s = self.seat_mod.seat(["bash", "-c", "true"], self.tmp.name, raw, {}, "t1 · close")
            list(s.lines())
        finally:
            os.environ.pop("SMIDJA_SEAT_DIR")
        self.assertTrue(list(seats.glob("*.pane")))
        closed = self.seat_mod.close_panes(seats)
        self.assertTrue(closed)
        self.assertIn(f"pane close {closed[0]}", self.log.read_text())
        self.assertFalse(list(seats.glob("*.pane")))

    def test_a_failing_turn_reports_its_code_and_keeps_its_pane(self):
        raw = Path(self.tmp.name) / "turn2" / "raw_output.jsonl"
        s = self.seat_mod.seat(["bash", "-c", "echo boom >&2; exit 7"], self.tmp.name, raw, {}, "t1 · demo")
        list(s.lines())
        self.assertEqual(s.returncode, 7)
        self.assertIn("boom", s.stderr)
        s.finish()
        self.assertNotIn("pane close", self.log.read_text())

    def test_a_second_turn_gets_its_own_pane_in_the_same_workspace(self):
        for n in ("a", "b"):
            raw = Path(self.tmp.name) / n / "raw_output.jsonl"
            s = self.seat_mod.seat(["true"], self.tmp.name, raw, {}, n)
            list(s.lines())
        calls = self.log.read_text()
        self.assertEqual(calls.count("workspace create"), 1)
        self.assertIn("pane split w9:p1", calls)


class TestModelInheritance(unittest.TestCase):
    """An agent with no model of its own inherits the env's choice, not the hoard's empty default."""

    def test_builder_inherits_the_env_model(self):
        sys.path.insert(0, str(FACTORY / "engine"))
        try:
            from smidja_modules import agents
        except ImportError as e:  # the runner suite runs on bare python; the engine needs its pip deps
            self.skipTest(f"engine deps not installed: {e}")
        with tempfile.TemporaryDirectory() as d:
            saved = {k: os.environ.get(k) for k in ("SMIDJA_LOCAL_MODEL", "YMIR_HOME", "YMIR_HOARD",
                                                    "YMIR_AGENTS_YAML", "YMIR_SETTINGS_DIR")}
            for k in ("YMIR_HOME", "YMIR_HOARD", "YMIR_AGENTS_YAML", "YMIR_SETTINGS_DIR"):
                os.environ.pop(k, None)
            os.environ["SMIDJA_LOCAL_MODEL"] = "prov/model-x"
            agents._HOARD_CACHE.clear()
            try:
                cfg = agents.load_config(str(FACTORY / "engine" / "smidja_smidja_config" / "smidja.config.yaml"))
                self.assertEqual(agents.resolve(cfg, "builder").model, "prov/model-x")
            finally:
                for k, v in saved.items():
                    if v is None:
                        os.environ.pop(k, None)
                    else:
                        os.environ[k] = v
                agents._HOARD_CACHE.clear()


if __name__ == "__main__":
    unittest.main()
