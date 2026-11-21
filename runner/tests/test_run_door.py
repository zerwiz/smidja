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
