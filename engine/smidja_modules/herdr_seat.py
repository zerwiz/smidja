"""The herdr seat road: an optional adapter that seats each agent turn in a visible pane.

The smithy's default runtime is `internal`: the engine spawns every agent headless
inside its own process tree. With `SMIDJA_AGENT_RUNTIME=herdr` each agent turn is
seated instead in a pane of a herdr workspace on THIS machine, so a person can watch
the turn and steer it by hand. The engine still reads the same JSON event stream,
because the pane writes it to the same raw-output file the engine tails.

Everything is environment-driven; nothing here names a host or a person:

  SMIDJA_AGENT_RUNTIME   internal (default) | herdr
  SMIDJA_HERDR_BIN       the herdr command (default: herdr)
  SMIDJA_HERDR_LABEL     label prefix of the workspace (default: smidja)
  SMIDJA_RUN_ID          the run id, used in the workspace label
  SMIDJA_HERDR_KEEP      1 = leave the pane open after a clean turn (a failed turn is always kept)
  SMIDJA_HERDR_TIMEOUT   seconds one turn may take before it is given up (default 7200)

If herdr is absent or its server does not answer, the seat refuses by name
(`HerdrUnavailable`); the engine never silently falls back to the other runtime,
because a run that was asked to be watchable must not quietly become invisible.
"""

from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Iterator, Optional

RUNTIMES = ("internal", "herdr")
_workspace: dict = {}


class HerdrUnavailable(RuntimeError):
    """The herdr runtime was asked for and cannot be had."""


def runtime() -> str:
    value = (os.environ.get("SMIDJA_AGENT_RUNTIME") or "internal").strip().lower()
    return value if value in RUNTIMES else "internal"


def _bin() -> str:
    return os.environ.get("SMIDJA_HERDR_BIN", "herdr")


def _herdr(*args: str, timeout: int = 30) -> dict:
    exe = shutil.which(_bin())
    if not exe:
        raise HerdrUnavailable(f"the herdr runtime was asked for, but `{_bin()}` is not on PATH")
    try:
        out = subprocess.run([exe, *args], capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise HerdrUnavailable(f"`herdr {args[0]}` did not answer within {timeout}s")
    if out.returncode != 0:
        raise HerdrUnavailable(f"`herdr {' '.join(args[:2])}` failed: {(out.stderr or out.stdout).strip()[-300:]}")
    try:
        return json.loads(out.stdout) if out.stdout.strip() else {}
    except ValueError:
        return {}


def available() -> tuple[bool, str]:
    """(ok, reason) — herdr is on PATH and its server answers."""
    try:
        _herdr("workspace", "list", timeout=10)
        return True, "herdr answers"
    except HerdrUnavailable as e:
        return False, str(e)


def _find(obj, key):
    """First value of `key` anywhere in a nested herdr answer."""
    if isinstance(obj, dict):
        if key in obj:
            return obj[key]
        for v in obj.values():
            hit = _find(v, key)
            if hit is not None:
                return hit
    elif isinstance(obj, list):
        for v in obj:
            hit = _find(v, key)
            if hit is not None:
                return hit
    return None


def _first_pane() -> str:
    """The pane every turn splits from: one workspace per run, made on first use."""
    if _workspace.get("pane"):
        return _workspace["pane"]
    label = f"{os.environ.get('SMIDJA_HERDR_LABEL', 'smidja')} {os.environ.get('SMIDJA_RUN_ID', os.getpid())}"
    made = _herdr("workspace", "create", "--label", label, "--no-focus")
    pane = _find(made, "pane_id") or _find(made, "root_pane_id")
    workspace = _find(made, "workspace_id")
    if not pane and workspace:
        pane = _find(_herdr("pane", "list", "--workspace", str(workspace)), "pane_id")
    if not pane:
        raise HerdrUnavailable(f"herdr made a workspace but named no pane: {json.dumps(made)[:200]}")
    _workspace.update(pane=str(pane), workspace=str(workspace or ""))
    return _workspace["pane"]


def _new_pane(cwd: str) -> str:
    base = _first_pane()
    if not _workspace.get("used"):
        _workspace["used"] = True          # the workspace's own first pane serves the first turn
        return base
    made = _herdr("pane", "split", base, "--direction", "down", "--cwd", cwd, "--no-focus")
    pane = _find(made, "pane_id")
    if not pane:
        raise HerdrUnavailable(f"herdr split named no pane: {json.dumps(made)[:200]}")
    return str(pane)


class Seat:
    """One agent turn seated in a pane. Iterate `lines()` for the JSON event stream."""

    def __init__(self, argv: list[str], cwd: str, raw_path: Path, env: dict, title: str):
        self.raw_path = raw_path
        self.rc_path = raw_path.with_suffix(raw_path.suffix + ".rc")
        self.err_path = raw_path.with_suffix(raw_path.suffix + ".err")
        # The AGENT's own pid, written by the seat script just before it execs the agent
        # (run audit, fault 8): herdr's process-info names the pane's shell, and a stop
        # sent there never reached the agent.
        self.pid_path = raw_path.with_suffix(raw_path.suffix + ".pid")
        self.returncode: Optional[int] = None
        self.pane = ""
        self.stderr = ""
        self._timeout = int(os.environ.get("SMIDJA_HERDR_TIMEOUT", "7200"))
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        for p in (self.rc_path, self.err_path, self.pid_path):
            p.unlink(missing_ok=True)
        self.pane = _new_pane(cwd)
        # Where a stop finds this run's panes to close them (SMIDJA_SEAT_DIR is set by the
        # runner per run; beside the raw stream otherwise).
        seat_dir = Path(os.environ.get("SMIDJA_SEAT_DIR") or raw_path.parent)
        try:
            seat_dir.mkdir(parents=True, exist_ok=True)
            (seat_dir / f"{self.pane.replace(':', '_')}.pane").write_text(self.pane)
        except OSError:
            pass
        # The pane's shell runs the turn; the tee filter writes the raw stream the engine
        # tails and prints a readable view for the person watching.
        tee = f"{shlex.quote(sys.executable)} {shlex.quote(str(Path(__file__).with_name('herdr_tee.py')))} {shlex.quote(str(raw_path))}"
        exports = " ".join(f"{k}={shlex.quote(v)}" for k, v in env.items() if k.startswith(("SMIDJA_", "PI_")))
        script = raw_path.with_suffix(raw_path.suffix + ".seat.sh")
        script.write_text(
            "#!/usr/bin/env bash\n"
            f"cd {shlex.quote(cwd)} || exit 1\n"
            f"printf '\\n== %s ==\\n' {shlex.quote(title)}\n"
            f"{exports} bash -c {shlex.quote('echo $$ > ' + shlex.quote(str(self.pid_path)) + '; exec \"$@\"')} agent {shlex.join(argv)}"
            f" 2> >(tee {shlex.quote(str(self.err_path))} >&2) | {tee}\n"
            f"echo ${{PIPESTATUS[0]}} > {shlex.quote(str(self.rc_path))}\n")
        _herdr("pane", "run", self.pane, f"clear; bash {shlex.quote(str(script))}")

    def pid(self) -> int:
        """The agent's own pid (from the seat script), waiting briefly for it to start;
        the pane's process only as a last resort."""
        for _ in range(40):
            try:
                text = self.pid_path.read_text().strip()
                if text:
                    return int(text)
            except (OSError, ValueError):
                pass
            time.sleep(0.05)
        try:
            info = _herdr("pane", "process-info", self.pane)
            return int(_find(info, "pid") or 0)
        except (HerdrUnavailable, ValueError):
            return 0

    def lines(self) -> Iterator[str]:
        deadline = time.time() + self._timeout
        pos = 0
        while True:
            done = self.rc_path.exists()
            if self.raw_path.exists():
                with self.raw_path.open("r") as fh:
                    fh.seek(pos)
                    while True:
                        chunk = fh.readline()
                        if not chunk or not chunk.endswith("\n"):
                            break
                        pos = fh.tell()
                        yield chunk
            if done:
                break
            if time.time() > deadline:
                self.returncode = 124
                self.stderr = f"the seated turn did not finish within {self._timeout}s"
                return
            time.sleep(0.3)
        try:
            self.returncode = int(self.rc_path.read_text().strip() or 1)
        except ValueError:
            self.returncode = 1
        self.stderr = self.err_path.read_text(errors="replace") if self.err_path.exists() else ""

    def finish(self) -> None:
        keep = os.environ.get("SMIDJA_HERDR_KEEP") == "1" or self.returncode != 0
        if keep:
            return
        try:
            if self.pane != _workspace.get("pane"):     # the workspace's own first pane stays
                _herdr("pane", "close", self.pane)
        except HerdrUnavailable:
            pass


def seat(argv: list[str], cwd: str, raw_path: Path, env: dict, title: str) -> Seat:
    return Seat(argv, cwd, raw_path, env, title)


def close_panes(seat_dir: Path) -> list[str]:
    """Close every pane a run seated (used by stop). A pane already gone is not an error."""
    closed = []
    for f in sorted(Path(seat_dir).glob("*.pane")):
        pane = f.read_text().strip()
        try:
            _herdr("pane", "close", pane)
            closed.append(pane)
        except HerdrUnavailable:
            pass
        f.unlink(missing_ok=True)
    return closed
