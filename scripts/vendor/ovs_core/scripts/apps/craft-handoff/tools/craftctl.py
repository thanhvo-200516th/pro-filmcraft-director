"""craftctl — drive FilmCraft / EffectCraft through their localhost control port (JSON lines).

Every session starts its own app instance on its own X display (Xephyr, default :93) with its own
data / config folder, so the FilmCraft or EffectCraft window the user has open is never touched.

    with Craft("filmcraft", workdir) as fc:
        fc.cmd("file.newSequence", {"name": "Main", "width": 1080, "height": 1920, "fps": 25})
        fc.cmd("file.saveAs", {"path": "/abs/out.fcproj"})

`cmd` runs a menu/engine command (`engine.execute`); `rpc` calls a raw method such as
`engine.commands`. A reply with ok=false raises CraftError carrying the app's own message.
Env: CRAFT_DISPLAY (default :93; ":0" shows the app on the real desktop), CRAFT_BIN_DIR.
"""

from __future__ import annotations

import json
import os
import secrets
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

BIN_DIR = Path(os.environ.get("CRAFT_BIN_DIR", str(Path.home() / ".local/bin")))
DEFAULT_DISPLAY = os.environ.get("CRAFT_DISPLAY", ":93")
START_TIMEOUT_S = 60
TICKS_PER_SECOND = 254_016_000_000          # FilmCraft time unit (same as Premiere)
X11_SOCKET_DIR = Path("/tmp/.X11-unix")


class CraftError(RuntimeError):
    """The app answered ok=false, or could not be started."""


def ticks(seconds: float) -> int:
    return int(round(seconds * TICKS_PER_SECOND))


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def display_alive(display: str) -> bool:
    """True only if an X server ANSWERS on the local socket of `display` (a leftover /tmp/.X11-unix/Xn file from a dead
    server is not trusted: that made FilmCraft exit at start on :93)."""
    sock_path = X11_SOCKET_DIR / f"X{display.lstrip(':').split('.')[0]}"
    if not sock_path.exists():
        return False
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
        s.settimeout(1.0)
        try:
            s.connect(str(sock_path))
        except OSError:
            return False
    return True


def ensure_display(display: str = DEFAULT_DISPLAY) -> str:
    """Start a Xephyr / Xvfb server on `display` unless an X server already answers there (probed, not assumed)."""
    if display_alive(display):
        return display
    server = os.environ.get("CRAFT_X_SERVER") or ("Xephyr" if shutil.which("Xephyr") else "Xvfb")   # Xvfb: server/Docker không màn hình
    if not shutil.which(server):
        raise CraftError(f"no X server on {display} and {server} is not installed")
    extra = ["-title", "craft-handoff"] if server == "Xephyr" else []
    subprocess.Popen(["setsid", server, display, "-screen", *(["1280x800"] if server == "Xephyr" else ["0", "1280x800x24"]), "-ac", *extra],
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     start_new_session=True)
    for _ in range(50):
        if display_alive(display):
            return display
        time.sleep(0.1)
    raise CraftError(f"{server} did not start on {display}")


class Craft:
    """One isolated FilmCraft or EffectCraft instance under control."""

    def __init__(self, app: str, workdir: str | Path, display: str | None = None,
                 args: tuple[str, ...] = (), isolate_config: bool = True):
        if app not in ("filmcraft", "effectcraft"):
            raise CraftError(f"unknown app {app!r}")
        self.app = app
        self.workdir = Path(workdir)
        self.workdir.mkdir(parents=True, exist_ok=True)
        self.display = ensure_display(display or DEFAULT_DISPLAY)
        self.port = _free_port()
        self.token = secrets.token_hex(32)
        env = {**os.environ, "DISPLAY": self.display, f"{app.upper()}_CONTROL_TOKEN": self.token}
        cmd = [str(BIN_DIR / app), "--control", str(self.port)]
        if app == "filmcraft":
            cmd += ["--data-dir", str(self.workdir / "fcdata"), "--no-recover", *(args or ("--empty",))]
        else:
            if isolate_config:
                env["XDG_CONFIG_HOME"] = str(self.workdir / "ecconfig")
            cmd += list(args)
        self.log = self.workdir / f"{app}.log"
        self.proc = subprocess.Popen(cmd, env=env, stdin=subprocess.DEVNULL,
                                     stdout=open(self.log, "w"), stderr=subprocess.STDOUT)
        self.sock = self._connect()
        self.reader = self.sock.makefile("r", encoding="utf-8")
        self._id = 0

    def _connect(self) -> socket.socket:
        deadline = time.monotonic() + START_TIMEOUT_S
        while time.monotonic() < deadline:
            if self.proc.poll() is not None:
                raise CraftError(f"{self.app} exited at start — see {self.log}")
            try:
                return socket.create_connection(("127.0.0.1", self.port), timeout=900)
            except OSError:
                time.sleep(0.3)
        self.proc.kill()
        raise CraftError(f"{self.app} control port {self.port} did not open — see {self.log}")

    def rpc(self, method: str, params: dict | None = None):
        self._id += 1
        msg = {"id": self._id, "token": self.token, "method": method}
        if params is not None:
            msg["params"] = params
        self.sock.sendall((json.dumps(msg, ensure_ascii=False) + "\n").encode("utf-8"))
        line = self.reader.readline()
        if not line:
            raise CraftError(f"{self.app} closed the control connection during {method} — see {self.log}")
        reply = json.loads(line)
        if not reply.get("ok"):
            raise CraftError(f"{self.app} {method}: {reply.get('error')}")
        return reply.get("result")

    def cmd(self, command: str, params: dict | None = None):
        # FilmCraft >= 0.20 answers "still starting; send the request again" while its engine boots: retry that reply only.
        deadline = time.monotonic() + float(os.environ.get("CRAFT_START_WAIT_S", "60"))
        while True:
            try:
                return self.rpc("engine.execute", {"command": command, "params": params or {}})
            except CraftError as exc:
                if "still starting" not in str(exc) or time.monotonic() >= deadline:
                    raise
                time.sleep(0.5)

    def pipeline(self, cmds: list[tuple[str, dict]], batch: int = 100) -> None:
        """Gửi dồn nhiều lệnh không cần đọc kết quả (đặt keyframe…): FilmCraft xử lý ~45 ms / lệnh khi gửi từng lệnh,
        ~24 ms khi gửi dồn (đo 2026-11-05). Thứ tự giữ nguyên; lỗi đầu tiên → CraftError."""
        for i in range(0, len(cmds), batch):
            part, buf = cmds[i:i + batch], []
            for command, params in part:
                self._id += 1
                buf.append(json.dumps({"id": self._id, "token": self.token, "method": "engine.execute",
                                       "params": {"command": command, "params": params}}, ensure_ascii=False))
            self.sock.sendall(("\n".join(buf) + "\n").encode("utf-8"))
            errs = []
            for command, _ in part:
                line = self.reader.readline()
                if not line:
                    raise CraftError(f"{self.app} closed the control connection during {command} — see {self.log}")
                reply = json.loads(line)
                if not reply.get("ok"):
                    errs.append(f"{command}: {reply.get('error')}")
            if errs:
                raise CraftError(f"{self.app} engine.execute: {errs[0]} (+{len(errs) - 1} lỗi khác)")

    def close(self) -> None:
        try:
            self.cmd("app.quit")
        except (CraftError, OSError, ValueError) as exc:  # app may already be gone; still terminate below
            print(f"craftctl: warning: app.quit failed ({type(exc).__name__}: {exc})", file=sys.stderr)
        try:
            self.proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        self.sock.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
