import streamlit as st
import json
import os
import time
import psutil
import requests
import subprocess
from pathlib import Path
from streamlit.components.v1 import html

# --- Configuration & State ---
st.set_page_config(page_title="Gemini OP v1.8 Continuous", layout="wide", page_icon="💂‍♂️")

def get_repo_root():
    return Path(os.environ.get("GEMINI_OP_REPO_ROOT", Path(__file__).resolve().parents[1]))

REPO_ROOT = get_repo_root()
PID_FILE = REPO_ROOT / ".gemini/current_mission.pid"

def get_latest_job():
    jobs_dir = REPO_ROOT / ".agent-jobs"
    if not jobs_dir.exists(): return None
    subdirs = [d for d in jobs_dir.iterdir() if d.is_dir() and d.name != "latest"]
    if not subdirs: return None
    return max(subdirs, key=lambda p: p.stat().st_mtime)

latest_job = get_latest_job()

# --- Actions ---
def kill_current_mission():
    if PID_FILE.exists():
        try:
            pid = int(PID_FILE.read_text().strip())
            parent = psutil.Process(pid)
            for child in parent.children(recursive=True):
                child.terminate()
            parent.terminate()
            PID_FILE.unlink()
            return True
        except:
            return False
    return False

def send_chat_message(content, role="Commander"):
    if latest_job:
        # Use relative path or absolute path
        bridge_script = REPO_ROOT / "scripts/chat_bridge.py"
        cmd = ["python", str(bridge_script), str(latest_job), role, content]
        subprocess.run(cmd)

# --- UI Setup ---
st.sidebar.title("💎 Gemini OP")
st.sidebar.markdown("**Status:** `CONTINUOUS PRESENCE` (v1.8)")

# Sidebar: System Health
st.sidebar.header("⚖️ Governance & Health")
if st.sidebar.button("💀 Emergency Kill", use_container_width=True, key="btn_emergency_kill"):
    kill_current_mission()
    st.rerun()

health = {"ram": psutil.virtual_memory().percent}
st.sidebar.metric("RAM Usage", f"{health['ram']}%")
st.sidebar.caption(f"PID: {PID_FILE.read_text() if PID_FILE.exists() else 'None'}")

# --- Main Chat Interface ---
st.title("💂‍♂️ Operations Manager: Direct Link")

if not latest_job:
    st.info("System Ready. Commander, please state your operational goal or just say hello.")
else:
    state_dir = latest_job / "state"
    history_file = state_dir / "chat_history.jsonl"
    brief_path = state_dir / "consolidated_brief.md"
    dec_path = state_dir / "decision.json"

    # Display Chat History
    if history_file.exists():
        with open(history_file, "r", encoding="utf-8") as f:
            for i, line in enumerate(f):
                msg = json.loads(line)
                with st.chat_message(msg["role"]):
                    st.markdown(msg["content"])

    # Governance Briefing
    if brief_path.exists() and not dec_path.exists():
        with st.chat_message("Deputy"):
            st.markdown("### 🛡️ Strategic Authorization Required")
            st.markdown(brief_path.read_text(encoding="utf-8"))
            c1, c2 = st.columns(2)
            if c1.button("✅ PROCEED", type="primary", use_container_width=True, key="btn_proceed_mission"):
                dec_path.write_text(json.dumps({"action": "PROCEED"}), encoding="utf-8")
                send_chat_message("Commander approved the plan. Resuming operations.", role="Deputy")
                st.rerun()
            if c2.button("🚫 VETO", use_container_width=True, key="btn_veto_mission"):
                dec_path.write_text(json.dumps({"action": "VETO"}), encoding="utf-8")
                send_chat_message("Commander vetoed the plan.", role="Deputy")
                st.rerun()

# Chat Input
prompt = st.chat_input("Commander's Intent...", key="chat_commander_intent")
if prompt:
    if not latest_job:
        # Start a new "Initial Chat" job if none active
        # This will create the job dir so chat can proceed
        proc = subprocess.Popen(
            ["powershell.exe", "-File", "scripts/chief_of_staff_orchestrator.ps1", "-Prompt", prompt, "-RepoRoot", str(REPO_ROOT)],
            cwd=str(REPO_ROOT),
            creationflags=subprocess.CREATE_NEW_CONSOLE
        )
        PID_FILE.write_text(str(proc.pid))
        st.toast("Connection Established!", icon="🚀")
        time.sleep(1)
        st.rerun()
    else:
        # Send message to current job history
        send_chat_message(prompt)
        st.rerun()

# --- Auto-Refresh ---
# If the last message is from Commander, refresh faster to catch the Deputy's response
refresh_rate = 2
if latest_job:
    history_file = latest_job / "state" / "chat_history.jsonl"
    if history_file.exists():
        lines = history_file.read_text(encoding="utf-8").splitlines()
        if lines:
            last_msg = json.loads(lines[-1])
            if last_msg["role"] == "Commander":
                refresh_rate = 1

time.sleep(refresh_rate)
st.rerun()
