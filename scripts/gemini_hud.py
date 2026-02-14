from __future__ import annotations

import argparse
import json
import os
import queue
import subprocess
import threading
import time
import datetime as dt
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Optional

import tkinter as tk
from tkinter import messagebox, simpledialog
from tkinter import ttk

try:
    import pystray  # type: ignore
    from PIL import Image, ImageDraw
except Exception:
    pystray = None
    Image = None
    ImageDraw = None


REPO_ROOT = Path(os.environ.get("GEMINI_OP_REPO_ROOT", Path(__file__).resolve().parent.parent))
WATCHDOG_STATUS_PATH = REPO_ROOT / "ramshare" / "state" / "watchdog_status.json"
WATCHDOG_AUDIT_PATH = REPO_ROOT / "ramshare" / "state" / "audit" / "watchdog.jsonl"
SECURITY_ALERT_PATH = REPO_ROOT / "ramshare" / "state" / "audit" / "security_alerts.jsonl"
NOTIFY_LOG_PATH = REPO_ROOT / "mcp" / "data" / "notifications.log"
POLICY_PATH = REPO_ROOT / "mcp" / "policy_proxy" / "policy.json"
MCP_HEALTH_PATH = REPO_ROOT / "ramshare" / "state" / "mcp_health.json"
HUD_ALIVE_PATH = REPO_ROOT / "ramshare" / "state" / "hud_alive.json"
STOP_ALL_PATH = REPO_ROOT / "STOP_ALL_AGENTS.flag"
STOP_RAM_PATH = REPO_ROOT / "ramshare" / "state" / "STOP"

WATCHDOG_START_SCRIPT = REPO_ROOT / "scripts" / "start-watchdog.ps1"
WATCHDOG_STOP_SCRIPT = REPO_ROOT / "scripts" / "stop-watchdog.ps1"


@dataclass
class HudState:
    ts: float
    active_profile: str
    watchdog_ok: bool
    watchdog_last_heartbeat_age_s: float
    containment_required: bool
    containment_ok: bool
    sidecar_ok: bool
    stop_all: bool
    stop_ramshare: bool
    mcp_total: int
    mcp_healthy: int
    mcp_unhealthy: int
    last_critical_alert: str
    last_critical_alert_ts: Optional[float]
    data_stale: bool
    read_errors: int
    stale_reason: str
    start_disabled_reason: str
    last_refresh_iso: str


def _now() -> float:
    return time.time()


def _iso(ts: float) -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts))


def _safe_read_json(path: Path) -> tuple[Optional[Dict[str, Any]], Optional[str]]:
    try:
        if not path.exists():
            return None, f"missing:{path.name}"
        return json.loads(path.read_text(encoding="utf-8-sig")), None
    except Exception as e:
        return None, f"invalid:{path.name}:{e}"


class JsonlTailer:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.offset = 0
        self.last_size = 0

    def read_new(self) -> list[Dict[str, Any]]:
        rows: list[Dict[str, Any]] = []
        if not self.path.exists():
            self.offset = 0
            self.last_size = 0
            return rows
        size = self.path.stat().st_size
        if size < self.offset:
            self.offset = 0
        with self.path.open("rb") as f:
            f.seek(self.offset)
            blob = f.read()
            self.offset = f.tell()
        self.last_size = size
        if not blob:
            return rows
        for line in blob.decode("utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
        return rows


class StateBuilder:
    def __init__(self, warn_age_s: int, crit_age_s: int, stale_data_s: int, alert_window_s: int = 120) -> None:
        self.warn_age_s = warn_age_s
        self.crit_age_s = crit_age_s
        self.stale_data_s = stale_data_s
        self.alert_window_s = max(60, int(alert_window_s))
        self.tailer_watchdog = JsonlTailer(WATCHDOG_AUDIT_PATH)
        self.tailer_security = JsonlTailer(SECURITY_ALERT_PATH)
        self.tailer_notify = JsonlTailer(NOTIFY_LOG_PATH)
        self.last_critical_alert = "none"
        self.last_critical_alert_ts: Optional[float] = None
        self.last_good_watchdog: Optional[Dict[str, Any]] = None
        self.last_good_policy: Optional[Dict[str, Any]] = None
        self.read_errors = 0

    def _event_ts(self, row: Dict[str, Any]) -> float:
        ts = row.get("timestamp")
        if isinstance(ts, (int, float)):
            return float(ts)
        iso = row.get("ts")
        if isinstance(iso, str):
            try:
                return dt.datetime.fromisoformat(iso).timestamp()
            except Exception:
                pass
        return _now()

    def _recent(self, row: Dict[str, Any]) -> bool:
        return (_now() - self._event_ts(row)) <= self.alert_window_s

    def _scan_alerts(self) -> None:
        for row in self.tailer_security.read_new():
            if not self._recent(row):
                continue
            self.last_critical_alert = f"{row.get('type', 'alert')}: {row.get('details', {})}"
            self.last_critical_alert_ts = self._event_ts(row)
        for row in self.tailer_notify.read_new():
            if not self._recent(row):
                continue
            lvl = str(row.get("level", "")).lower()
            if lvl in {"critical", "error"}:
                self.last_critical_alert = str(row.get("message", "critical alert"))
                self.last_critical_alert_ts = self._event_ts(row)
        for row in self.tailer_watchdog.read_new():
            if row.get("ok") is False and self._recent(row):
                self.last_critical_alert = f"watchdog:{row.get('event')}"
                self.last_critical_alert_ts = self._event_ts(row)

    def build(self) -> HudState:
        self._scan_alerts()
        now = _now()
        stop_all = STOP_ALL_PATH.exists()
        stop_ram = STOP_RAM_PATH.exists()

        wd_raw, wd_err = _safe_read_json(WATCHDOG_STATUS_PATH)
        if wd_raw is not None:
            self.last_good_watchdog = wd_raw
        elif wd_err:
            self.read_errors += 1

        policy_raw, policy_err = _safe_read_json(POLICY_PATH)
        if policy_raw is not None:
            self.last_good_policy = policy_raw
        elif policy_err:
            self.read_errors += 1

        wd = self.last_good_watchdog or {}
        policy = self.last_good_policy or {}

        profile = str(wd.get("profile") or "unknown")
        wd_ts_text = str(wd.get("ts") or "")
        wd_epoch: Optional[float] = None
        try:
            wd_epoch = time.mktime(time.strptime(wd_ts_text, "%Y-%m-%dT%H:%M:%S%z"))
        except Exception:
            wd_epoch = None
        if wd_epoch is None and WATCHDOG_STATUS_PATH.exists():
            wd_epoch = WATCHDOG_STATUS_PATH.stat().st_mtime
        age = (now - wd_epoch) if wd_epoch else 1e9

        targets = wd.get("targets") if isinstance(wd.get("targets"), dict) else {}
        mcp_total = 0
        mcp_healthy = 0
        sidecar_ok = False
        for tid, info in targets.items():
            healthy = bool((info or {}).get("healthy"))
            if tid == "sidecar-window":
                sidecar_ok = healthy
                continue
            mcp_total += 1
            if healthy:
                mcp_healthy += 1
        mcp_unhealthy = max(0, mcp_total - mcp_healthy)

        mcp_raw, _ = _safe_read_json(MCP_HEALTH_PATH)
        if isinstance(mcp_raw, dict):
            mcp_total = int(mcp_raw.get("total", mcp_total))
            mcp_healthy = int(mcp_raw.get("healthy", mcp_healthy))
            mcp_unhealthy = max(0, int(mcp_raw.get("unhealthy", mcp_unhealthy)))

        containment_required = bool(
            ((policy.get("ui_automation") or {}).get("require_sidecar_window", False))
        )
        containment_ok = containment_required and sidecar_ok

        data_stale = age > self.stale_data_s
        stale_reason = ""
        if data_stale:
            stale_reason = f"heartbeat stale ({int(age)}s)"
        elif wd_err:
            stale_reason = wd_err
        elif policy_err:
            stale_reason = policy_err

        watchdog_ok = age <= self.warn_age_s
        if age > self.crit_age_s:
            watchdog_ok = False

        start_disabled_reason = ""
        if stop_all or stop_ram:
            start_disabled_reason = "STOP mode active"
        elif not containment_required:
            start_disabled_reason = "containment disabled by policy"
        elif data_stale and profile == "unknown":
            start_disabled_reason = "watchdog status unavailable"

        return HudState(
            ts=now,
            active_profile=profile,
            watchdog_ok=watchdog_ok,
            watchdog_last_heartbeat_age_s=float(age),
            containment_required=containment_required,
            containment_ok=containment_ok,
            sidecar_ok=sidecar_ok,
            stop_all=stop_all,
            stop_ramshare=stop_ram,
            mcp_total=mcp_total,
            mcp_healthy=mcp_healthy,
            mcp_unhealthy=mcp_unhealthy,
            last_critical_alert=self.last_critical_alert,
            last_critical_alert_ts=self.last_critical_alert_ts,
            data_stale=data_stale,
            read_errors=self.read_errors,
            stale_reason=stale_reason,
            start_disabled_reason=start_disabled_reason,
            last_refresh_iso=_iso(now),
        )


class HudApp:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.root = tk.Tk()
        self.root.title("Gemini Command HUD")
        self.root.geometry("980x620")
        if args.always_on_top:
            self.root.wm_attributes("-topmost", 1)

        self.queue: queue.Queue[HudState] = queue.Queue(maxsize=2)
        self.stop_event = threading.Event()
        self.state: Optional[HudState] = None
        self.builder = StateBuilder(args.warn_age_s, args.crit_age_s, args.stale_data_s)
        self.tray_icon = None
        self.tray_queue: queue.Queue[str] = queue.Queue()
        self.quitting = False

        self._build_ui()
        self.worker = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker.start()
        if args.tray:
            self._start_tray()
        self.root.after(200, self._poll_queue)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        if args.start_hidden:
            self.root.after(50, self._hide_window)
        elif args.minimized:
            self.root.after(50, self.root.iconify)

    def _build_ui(self) -> None:
        self.banner = tk.Label(self.root, text="NORMAL MODE", bg="#2e7d32", fg="white", font=("Segoe UI", 11, "bold"))
        self.banner.pack(fill="x")

        self.top_text = tk.StringVar(value="Loading...")
        top = tk.Label(self.root, textvariable=self.top_text, anchor="w", padx=8, pady=8, font=("Segoe UI", 10))
        top.pack(fill="x")

        body = tk.Frame(self.root)
        body.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        body.grid_columnconfigure(0, weight=1, minsize=180)
        body.grid_columnconfigure(1, weight=3)
        body.grid_columnconfigure(2, weight=2, minsize=300)
        body.grid_rowconfigure(0, weight=1)

        left = tk.Frame(body, bd=1, relief="solid")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        tk.Label(left, text="Rooms", anchor="w", bg="#1f2937", fg="white", padx=8, pady=6, font=("Segoe UI", 10, "bold")).pack(fill="x")
        self.room_list = tk.Listbox(left, exportselection=False, font=("Segoe UI", 10))
        self.room_list.pack(fill="both", expand=True, padx=6, pady=6)
        for room in ("#ops", "#watchdog", "#policy", "#memory", "#trust"):
            self.room_list.insert("end", room)
        self.room_list.selection_set(0)
        self.room_list.bind("<<ListboxSelect>>", self._on_room_change)

        center = tk.Frame(body, bd=1, relief="solid")
        center.grid(row=0, column=1, sticky="nsew", padx=6)
        tk.Label(center, text="Conversation", anchor="w", bg="#1f2937", fg="white", padx=8, pady=6, font=("Segoe UI", 10, "bold")).pack(fill="x")
        transcript_wrap = tk.Frame(center)
        transcript_wrap.pack(fill="both", expand=True, padx=6, pady=6)
        transcript_scroll = tk.Scrollbar(transcript_wrap, orient="vertical")
        transcript_scroll.pack(side="right", fill="y")
        self.transcript = tk.Text(
            transcript_wrap,
            wrap="word",
            font=("Consolas", 10),
            bg="#f8fafc",
            yscrollcommand=transcript_scroll.set,
            state="disabled",
        )
        self.transcript.pack(fill="both", expand=True)
        transcript_scroll.config(command=self.transcript.yview)

        right = tk.Frame(body, bd=1, relief="solid")
        right.grid(row=0, column=2, sticky="nsew", padx=(6, 0))
        tk.Label(right, text="Notebook", anchor="w", bg="#1f2937", fg="white", padx=8, pady=6, font=("Segoe UI", 10, "bold")).pack(fill="x")
        self.notebook = ttk.Notebook(right)
        self.notebook.pack(fill="both", expand=True, padx=6, pady=6)

        self.state_tab = tk.Frame(self.notebook)
        self.intents_tab = tk.Frame(self.notebook)
        self.memory_tab = tk.Frame(self.notebook)
        self.trust_tab = tk.Frame(self.notebook)
        self.policy_tab = tk.Frame(self.notebook)
        self.notebook.add(self.state_tab, text="State")
        self.notebook.add(self.intents_tab, text="Intents")
        self.notebook.add(self.memory_tab, text="Memory")
        self.notebook.add(self.trust_tab, text="Trust")
        self.notebook.add(self.policy_tab, text="Policy")

        self.grid = tk.Frame(self.state_tab)
        self.grid.pack(fill="both", expand=True)

        self.tiles: dict[str, tuple[tk.Frame, tk.StringVar]] = {}
        for i, key in enumerate(["watchdog", "sidecar", "mcp", "containment", "alerts", "freshness"]):
            frame = tk.Frame(self.grid, bd=1, relief="solid", bg="#eeeeee")
            frame.grid(row=i // 2, column=i % 2, sticky="nsew", padx=4, pady=4)
            self.grid.grid_rowconfigure(i // 2, weight=1)
            self.grid.grid_columnconfigure(i % 2, weight=1)
            title = tk.Label(frame, text=key.upper(), bg="#444", fg="white", anchor="w", padx=6)
            title.pack(fill="x")
            var = tk.StringVar(value="-")
            body_lbl = tk.Label(
                frame,
                textvariable=var,
                justify="left",
                anchor="nw",
                bg="#eeeeee",
                padx=8,
                pady=8,
                font=("Consolas", 10),
            )
            body_lbl.pack(fill="both", expand=True)
            self.tiles[key] = (frame, var)

        self.intents_text = self._build_tab_text(self.intents_tab)
        self.memory_text = self._build_tab_text(self.memory_tab)
        self.trust_text = self._build_tab_text(self.trust_tab)
        self.policy_text = self._build_tab_text(self.policy_tab)
        self._set_tab_text(self.intents_text, "No intents yet.")
        self._set_tab_text(self.memory_text, "No memory notes yet.")
        self._set_tab_text(self.trust_text, "No trust notes yet.")
        self._set_tab_text(self.policy_text, f"Policy source: {POLICY_PATH}")

        self.action_reason = tk.StringVar(value="")
        status = tk.Label(self.root, textvariable=self.action_reason, anchor="w", fg="#b71c1c", padx=8)
        status.pack(fill="x")

        command_bar = tk.Frame(self.root)
        command_bar.pack(fill="x", padx=8, pady=(0, 8))
        tk.Label(command_bar, text="Command", font=("Segoe UI", 9, "bold")).pack(side="left", padx=(0, 8))
        self.command_var = tk.StringVar(value="")
        self.command_entry = tk.Entry(command_bar, textvariable=self.command_var, font=("Consolas", 10))
        self.command_entry.pack(side="left", fill="x", expand=True)
        self.command_entry.bind("<Return>", self._on_submit_command)
        tk.Button(command_bar, text="Send", width=10, command=self._on_submit_command).pack(side="left", padx=(8, 0))
        tk.Label(command_bar, text="Use @agent message", fg="#555", padx=8).pack(side="left")

        self._append_transcript("system", "Chat HUD initialized.")

    def _build_tab_text(self, parent: tk.Frame) -> tk.Text:
        txt = tk.Text(parent, wrap="word", font=("Consolas", 10), bg="#f8fafc", state="disabled")
        txt.pack(fill="both", expand=True, padx=4, pady=4)
        return txt

    def _set_tab_text(self, widget: tk.Text, content: str) -> None:
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("end", content)
        widget.configure(state="disabled")

    def _active_room(self) -> str:
        sel = self.room_list.curselection()
        return self.room_list.get(sel[0]) if sel else "#ops"

    def _append_transcript(self, speaker: str, text: str, room: Optional[str] = None) -> None:
        room_name = room or self._active_room()
        stamp = _iso(_now())
        line = f"[{stamp}] {room_name} {speaker}: {text}\n"
        self.transcript.configure(state="normal")
        self.transcript.insert("end", line)
        self.transcript.see("end")
        self.transcript.configure(state="disabled")

    def _on_room_change(self, _event: Any = None) -> None:
        self._append_transcript("system", f"Switched to {self._active_room()}.")

    def _parse_command(self, raw: str) -> tuple[str, str]:
        text = raw.strip()
        if not text:
            return "agent", ""
        if text.startswith("@"):
            token, _, rest = text.partition(" ")
            agent = token[1:] or "agent"
            return agent, rest.strip()
        return "agent", text

    def _on_submit_command(self, _event: Any = None) -> None:
        raw = self.command_var.get().strip()
        if not raw:
            return
        self.command_var.set("")
        agent, body = self._parse_command(raw)
        if not body:
            body = "(no message body)"
        self._append_transcript("you", f"@{agent} {body}")
        self._set_tab_text(self.intents_text, f"last_target=@{agent}\nlast_message={body}")
        self.action_reason.set("UI-only command captured; execution actions are not wired in this phase.")

    def _write_hud_alive(self) -> None:
        HUD_ALIVE_PATH.parent.mkdir(parents=True, exist_ok=True)
        payload = {"ts": _iso(_now()), "pid": os.getpid(), "state": "alive"}
        HUD_ALIVE_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _worker_loop(self) -> None:
        while not self.stop_event.is_set():
            try:
                st = self.builder.build()
                self._write_hud_alive()
                while True:
                    try:
                        self.queue.get_nowait()
                    except queue.Empty:
                        break
                self.queue.put_nowait(st)
            except Exception:
                pass
            time.sleep(max(1, self.args.refresh_seconds))

    def _poll_queue(self) -> None:
        try:
            st = self.queue.get_nowait()
            self.state = st
            self._render(st)
        except queue.Empty:
            pass
        self._poll_tray_queue()
        if not self.stop_event.is_set():
            self.root.after(200, self._poll_queue)

    def _poll_tray_queue(self) -> None:
        while True:
            try:
                cmd = self.tray_queue.get_nowait()
            except queue.Empty:
                break
            if cmd == "show":
                self._show_window()
            elif cmd == "hide":
                self._hide_window()
            elif cmd == "stop_all":
                STOP_ALL_PATH.write_text("STOP\n", encoding="utf-8")
                STOP_RAM_PATH.parent.mkdir(parents=True, exist_ok=True)
                STOP_RAM_PATH.write_text("STOP\n", encoding="utf-8")
            elif cmd == "clear_stop":
                for p in (STOP_ALL_PATH, STOP_RAM_PATH):
                    try:
                        p.unlink()
                    except FileNotFoundError:
                        pass
            elif cmd == "quit":
                self.quitting = True
                self._on_close()

    def _tile(self, key: str, body: str, color: str) -> None:
        frame, var = self.tiles[key]
        var.set(body)
        frame.configure(bg=color)
        for child in frame.winfo_children():
            if isinstance(child, tk.Label) and child.cget("fg") != "white":
                child.configure(bg=color)

    def _render(self, st: HudState) -> None:
        self.top_text.set(
            f"profile={st.active_profile}  refresh={st.last_refresh_iso}  heartbeat_age={int(st.watchdog_last_heartbeat_age_s)}s  containment_required={st.containment_required}"
        )

        if st.stop_all or st.stop_ramshare:
            self.banner.config(text="STOP MODE ACTIVE", bg="#b71c1c")
        else:
            self.banner.config(text="NORMAL MODE", bg="#2e7d32")

        wd_color = "#c8e6c9"
        if st.watchdog_last_heartbeat_age_s > self.args.warn_age_s:
            wd_color = "#fff9c4"
        if st.watchdog_last_heartbeat_age_s > self.args.crit_age_s or st.data_stale:
            wd_color = "#ffcdd2"
        self._tile(
            "watchdog",
            f"ok={st.watchdog_ok}\nage={int(st.watchdog_last_heartbeat_age_s)}s\nstale={st.data_stale}",
            wd_color,
        )

        sidecar_color = "#c8e6c9" if st.sidecar_ok else "#fff9c4"
        self._tile("sidecar", f"sidecar_ok={st.sidecar_ok}\nprofile={st.active_profile}", sidecar_color)

        mcp_color = "#c8e6c9" if st.mcp_unhealthy == 0 else "#fff9c4"
        if st.mcp_total == 0 and st.active_profile in {"research", "full", "browser"}:
            mcp_color = "#ffcdd2"
        self._tile("mcp", f"healthy={st.mcp_healthy}/{st.mcp_total}\nunhealthy={st.mcp_unhealthy}", mcp_color)

        if not st.containment_required:
            containment_color = "#ffcdd2"
        elif st.containment_ok:
            containment_color = "#c8e6c9"
        else:
            containment_color = "#fff9c4"
        self._tile(
            "containment",
            f"required={st.containment_required}\nok={st.containment_ok}\nsidecar_ok={st.sidecar_ok}",
            containment_color,
        )

        alert_ts = _iso(st.last_critical_alert_ts) if st.last_critical_alert_ts else "n/a"
        self._tile("alerts", f"last={alert_ts}\n{st.last_critical_alert[:220]}", "#eeeeee")

        freshness_color = "#c8e6c9" if not st.data_stale else "#fff9c4"
        if st.read_errors > 5:
            freshness_color = "#ffcdd2"
        self._tile("freshness", f"read_errors={st.read_errors}\nstale_reason={st.stale_reason or 'none'}", freshness_color)

        policy_summary = (
            f"containment_required={st.containment_required}\n"
            f"containment_ok={st.containment_ok}\n"
            f"sidecar_ok={st.sidecar_ok}\n"
            f"start_disabled_reason={st.start_disabled_reason or 'none'}\n"
            f"policy_path={POLICY_PATH}"
        )
        trust_summary = (
            f"stop_all={st.stop_all}\n"
            f"stop_ramshare={st.stop_ramshare}\n"
            f"last_critical_alert={st.last_critical_alert}\n"
            f"last_critical_alert_ts={_iso(st.last_critical_alert_ts) if st.last_critical_alert_ts else 'n/a'}"
        )
        memory_summary = (
            f"read_errors={st.read_errors}\n"
            f"data_stale={st.data_stale}\n"
            f"stale_reason={st.stale_reason or 'none'}\n"
            f"last_refresh={st.last_refresh_iso}"
        )
        self._set_tab_text(self.policy_text, policy_summary)
        self._set_tab_text(self.trust_text, trust_summary)
        self._set_tab_text(self.memory_text, memory_summary)
        self.action_reason.set(st.start_disabled_reason or "")

    def _run_ps(self, script: Path, args: list[str]) -> tuple[bool, str]:
        cmd = [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script),
        ] + args
        proc = subprocess.run(cmd, capture_output=True, text=True)
        ok = proc.returncode == 0
        msg = (proc.stdout or proc.stderr or "").strip()
        return ok, msg

    def _action_stop_all(self) -> None:
        value = simpledialog.askstring("Confirm STOP", "Type STOP to confirm emergency stop:", parent=self.root)
        if value != "STOP":
            return
        STOP_ALL_PATH.write_text("STOP\n", encoding="utf-8")
        STOP_RAM_PATH.parent.mkdir(parents=True, exist_ok=True)
        STOP_RAM_PATH.write_text("STOP\n", encoding="utf-8")
        messagebox.showinfo("STOP", "STOP flags created.")

    def _action_clear_stop(self) -> None:
        if not messagebox.askyesno("Clear STOP", "Remove STOP flags?"):
            return
        for p in (STOP_ALL_PATH, STOP_RAM_PATH):
            try:
                p.unlink()
            except FileNotFoundError:
                pass
        messagebox.showinfo("STOP", "STOP flags cleared.")

    def _action_start_watchdog(self) -> None:
        profile = self.state.active_profile if self.state else "sidecar-operator"
        if not messagebox.askyesno("Start Watchdog", f"Start watchdog for profile '{profile}'?"):
            return
        ok, msg = self._run_ps(WATCHDOG_START_SCRIPT, ["-Profile", profile, "-AutoRestartSidecar"])
        if ok:
            messagebox.showinfo("Watchdog", msg or "Started.")
        else:
            messagebox.showerror("Watchdog", msg or "Failed.")

    def _action_stop_watchdog(self) -> None:
        profile = self.state.active_profile if self.state else "sidecar-operator"
        if not messagebox.askyesno("Stop Watchdog", f"Stop watchdog for profile '{profile}'?"):
            return
        ok, msg = self._run_ps(WATCHDOG_STOP_SCRIPT, ["-Profile", profile])
        if ok:
            messagebox.showinfo("Watchdog", msg or "Stopped.")
        else:
            messagebox.showerror("Watchdog", msg or "Failed.")

    def _action_open_logs(self) -> None:
        try:
            os.startfile(str(REPO_ROOT / "ramshare" / "state" / "audit"))
        except Exception as e:
            messagebox.showerror("Open Logs", str(e))

    def _action_open_policy(self) -> None:
        try:
            os.startfile(str(POLICY_PATH))
        except Exception as e:
            messagebox.showerror("Open Policy", str(e))

    def _show_window(self) -> None:
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def _hide_window(self) -> None:
        self.root.withdraw()

    def _create_tray_image(self) -> Any:
        if Image is None or ImageDraw is None:
            return None
        img = Image.new("RGB", (64, 64), color=(34, 44, 65))
        draw = ImageDraw.Draw(img)
        draw.rectangle((8, 8, 56, 56), outline=(81, 181, 255), width=3)
        draw.rectangle((16, 20, 48, 28), fill=(81, 181, 255))
        draw.rectangle((16, 34, 40, 42), fill=(139, 199, 255))
        return img

    def _start_tray(self) -> None:
        if pystray is None:
            print("pystray not installed; tray mode disabled.")
            return
        icon_img = self._create_tray_image()
        if icon_img is None:
            return

        def _enqueue(cmd: str):
            def _handler(icon, item):  # noqa: ANN001
                self.tray_queue.put(cmd)
            return _handler

        menu = pystray.Menu(
            pystray.MenuItem("Show HUD", _enqueue("show")),
            pystray.MenuItem("Hide HUD", _enqueue("hide")),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("STOP ALL", _enqueue("stop_all")),
            pystray.MenuItem("Clear STOP", _enqueue("clear_stop")),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", _enqueue("quit")),
        )
        self.tray_icon = pystray.Icon("GEMINI_hud", icon_img, "Gemini HUD", menu)
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def _on_close(self) -> None:
        if self.args.tray and not self.quitting:
            self._hide_window()
            return
        self.stop_event.set()
        if self.tray_icon is not None:
            try:
                self.tray_icon.stop()
            except Exception:
                pass
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Gemini Command HUD")
    ap.add_argument("--refresh-seconds", type=int, default=2)
    ap.add_argument("--warn-age-s", type=int, default=8)
    ap.add_argument("--crit-age-s", type=int, default=24)
    ap.add_argument("--stale-data-s", type=int, default=30)
    ap.add_argument("--always-on-top", action="store_true")
    ap.add_argument("--minimized", action="store_true")
    ap.add_argument("--start-hidden", action="store_true")
    ap.add_argument("--tray", action="store_true", help="Enable system tray controls (requires pystray).")
    ap.add_argument("--headless-check", action="store_true", help="Build one state and print JSON.")
    return ap.parse_args()


def main() -> None:
    args = parse_args()
    if args.headless_check:
        st = StateBuilder(args.warn_age_s, args.crit_age_s, args.stale_data_s).build()
        print(json.dumps(asdict(st), indent=2))
        return
    HudApp(args).run()


if __name__ == "__main__":
    main()
