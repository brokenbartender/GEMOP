import streamlit as st
import json
import os
import time
import psutil
import requests
import subprocess
from pathlib import Path

# --- Configuration & State ---
st.set_page_config(page_title="Mission Control v2.0", layout="wide", page_icon="💂‍♂️")

def get_repo_root():
    return Path(os.environ.get("GEMINI_OP_REPO_ROOT", Path(__file__).resolve().parents[1]))

REPO_ROOT = get_repo_root()
PID_FILE = REPO_ROOT / ".gemini/current_mission.pid"
UNIVERSAL_CONTEXT_PATH = REPO_ROOT / "ramshare" / "state" / "universal_context.json"

def get_universal_context():
    if UNIVERSAL_CONTEXT_PATH.exists():
        try:
            return json.loads(UNIVERSAL_CONTEXT_PATH.read_text(encoding="utf-8"))
        except: pass
    return None

u_context = get_universal_context()

# Global Awareness Bar
if u_context:
    with st.container():
        c1, c2, c3 = st.columns([2, 3, 1])
        with c1:
            task_status = "🧠 **THINKING**" if u_context.get("is_processing") else f"🎯 **Task:** {u_context.get('current_task', 'Idle')}"
            st.markdown(task_status)
        with c2:
            st.caption(f"🧠 **Chain of Thought:** {u_context.get('lessons_summary', 'Awaiting context...')}")
        with c3:
            st.caption(f"⚡ **Load:** CPU {u_context.get('system_load', {}).get('cpu', 0)}% | RAM {u_context.get('system_load', {}).get('ram', 0)}%")
    st.divider()

# Custom CSS for Mobile-Responsive Executive Review
st.markdown("""
    <style>
    .stChatMessage {
        font-size: 1.1rem !important;
        max-width: 85% !important;
    }
    .stChatInput {
        position: fixed !important;
        bottom: 2rem !important;
    }
    /* Mobile adjustments */
    @media (max-width: 768px) {
        .stChatMessage {
            max-width: 100% !important;
            font-size: 1rem !important;
        }
    }
    </style>
""", unsafe_allow_html=True)

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
        bridge_script = REPO_ROOT / "scripts/chat_bridge.py"
        cmd = ["python", str(bridge_script), str(latest_job), role, content]
        subprocess.run(cmd)

# --- Sidebar: System Health ---
st.sidebar.title("💎 Gemini OP v2.0")
st.sidebar.markdown("**Status:** `OPERATIONAL`")

if st.sidebar.button("💀 Emergency Kill", use_container_width=True):
    kill_current_mission()
    st.rerun()

health = {"ram": psutil.virtual_memory().percent}
st.sidebar.metric("RAM Usage", f"{health['ram']}%")
st.sidebar.caption(f"PID: {PID_FILE.read_text() if PID_FILE.exists() else 'None'}")

# --- Main Chat Interface ---
st.title("💂‍♂️ Operations Manager")

if not latest_job:
    st.info("System Ready. Commander, please state your operational goal.")
else:
    state_dir = latest_job / "state"
    history_file = state_dir / "chat_history.jsonl"
    brief_path = state_dir / "consolidated_brief.md"
    dec_path = state_dir / "decision.json"
    
    # Staff Activity Logs (Collapsed)
    with st.expander("📂 Staff Activity & Logs", expanded=False):
        stdout_logs = list(latest_job.glob("*.stdout.log"))
        if stdout_logs:
            for log_file in stdout_logs:
                st.markdown(f"**{log_file.name}**")
                st.code(log_file.read_text(encoding="utf-8", errors="ignore")[-1000:])
        else:
            st.write("No active logs found.")

    # Display Chat History
    if history_file.exists():
        messages = []
        with open(history_file, "r", encoding="utf-8") as f:
            for line in f:
                messages.append(json.loads(line))
        
        for i, msg in enumerate(messages):
            role = "user" if msg["role"] == "Commander" else "assistant"
            with st.chat_message(role):
                # If it's the last message and it's from the Deputy, simulate streaming
                if i == len(messages) - 1 and msg["role"] == "Deputy" and "streamed" not in st.session_state.get(f"msg_{i}", []):
                    placeholder = st.empty()
                    full_text = ""
                    for char in msg["content"]:
                        full_text += char
                        placeholder.markdown(full_text + "▌")
                        time.sleep(0.01)
                    placeholder.markdown(full_text)
                    if "streamed_messages" not in st.session_state: st.session_state.streamed_messages = set()
                    st.session_state.streamed_messages.add(i)
                else:
                    st.markdown(msg["content"])

    # Thinking Spinner
    is_thinking = False
    if history_file.exists():
        lines = history_file.read_text(encoding="utf-8").splitlines()
        if lines:
            last_msg = json.loads(lines[-1])
            if last_msg["role"] == "Commander":
                is_thinking = True
    
    if is_thinking:
        with st.chat_message("assistant"):
            st.write("Thinking...")
            st.spinner("Deputy is processing...")

    # Governance Briefing
    if brief_path.exists() and not dec_path.exists():
        with st.chat_message("assistant"):
            st.markdown("### 🛡️ Strategic Authorization Required")
            st.markdown(brief_path.read_text(encoding="utf-8"))
            c1, c2 = st.columns(2)
            if c1.button("✅ PROCEED", type="primary", use_container_width=True):
                dec_path.write_text(json.dumps({"action": "PROCEED"}), encoding="utf-8")
                send_chat_message("Commander approved the plan. Resuming operations.", role="Deputy")
                st.rerun()
            if c2.button("🚫 VETO", use_container_width=True):
                dec_path.write_text(json.dumps({"action": "VETO"}), encoding="utf-8")
                send_chat_message("Commander vetoed the plan.", role="Deputy")
                st.rerun()

# Chat Input
if prompt := st.chat_input("Commander's Intent..."):
    if not latest_job:
        proc = subprocess.Popen(
            ["powershell.exe", "-File", "scripts/gemini_orchestrator.ps1", "-Prompt", prompt, "-RepoRoot", str(REPO_ROOT)],
            cwd=str(REPO_ROOT),
            creationflags=subprocess.CREATE_NEW_CONSOLE
        )
        PID_FILE.write_text(str(proc.pid))
        st.toast("Mission Initialized!", icon="🚀")
        # Initialize chat file immediately for the UI
        time.sleep(2)
        st.rerun()
    else:
        send_chat_message(prompt)
        st.rerun()

# Auto-Refresh Logic
if latest_job:
    time.sleep(2)
    st.rerun()
