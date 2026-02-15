import streamlit as st
import json
import os
import time
import psutil
import pandas as pd
import requests
import subprocess
from pathlib import Path
from datetime import datetime

# --- Configuration & Styling ---
st.set_page_config(page_title="Gemini-OP | Mission Control", layout="wide", page_icon="💎")

def get_repo_root():
    return Path(os.environ.get("GEMINI_OP_REPO_ROOT", Path(__file__).resolve().parents[1]))

REPO_ROOT = get_repo_root()
PID_FILE = REPO_ROOT / ".gemini/current_mission.pid"
UNIVERSAL_CONTEXT_PATH = REPO_ROOT / "ramshare" / "state" / "universal_context.json"
LESSONS_PATH = REPO_ROOT / "ramshare/learning/memory/lessons.md"
LEDGER_PATH = REPO_ROOT / "ramshare/state/queue/ledger.jsonl"

# Custom CSS for Enterprise Look
st.markdown("""
    <style>
    .stApp { background-color: #050505; color: #e0e0e0; }
    .stMetric { background-color: #111; border: 1px solid #333; padding: 10px; border-radius: 10px; }
    .stButton>button { border-radius: 8px; font-weight: 600; }
    .status-thinking { color: #3b82f6; animation: pulse 2s infinite; }
    @keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.5; } 100% { opacity: 1; } }
    </style>
""", unsafe_allow_html=True)

# --- Data Loaders ---
def get_universal_context():
    if UNIVERSAL_CONTEXT_PATH.exists():
        try: return json.loads(UNIVERSAL_CONTEXT_PATH.read_text(encoding="utf-8"))
        except: return {}
    return {}

def get_latest_job():
    jobs_dir = REPO_ROOT / ".agent-jobs"
    if not jobs_dir.exists(): return None
    subdirs = [d for d in jobs_dir.iterdir() if d.is_dir() and d.name != "latest"]
    if not subdirs: return None
    return max(subdirs, key=lambda p: p.stat().st_mtime)

def get_ledger():
    if not LEDGER_PATH.exists(): return []
    try:
        with open(LEDGER_PATH, "r", encoding="utf-8") as f:
            return [json.loads(line) for line in f if line.strip()]
    except: return []

# --- Actions ---
def kill_all_agents():
    (REPO_ROOT / "STOP_ALL_AGENTS.flag").touch()
    time.sleep(1)
    st.toast("Kill signal broadcasted!", icon="💀")

def nuclear_reset():
    reset_script = REPO_ROOT / "scripts/nuclear_reset.ps1"
    subprocess.Popen(["powershell.exe", "-File", str(reset_script)], creationflags=subprocess.CREATE_NEW_CONSOLE)
    st.toast("Nuclear Reset Initiated!", icon="☢️")

def send_chat_message(content, role="Commander"):
    job = get_latest_job()
    if job:
        bridge_script = REPO_ROOT / "scripts/chat_bridge.py"
        subprocess.run(["python", str(bridge_script), str(job), role, content])

# --- Main Layout ---
u_context = get_universal_context()
latest_job = get_latest_job()

# Header / Global Status
with st.container():
    c1, c2, c3, c4 = st.columns([2, 2, 2, 1])
    with c1:
        st.title("💎 Gemini-OP")
    with c2:
        status = "🧠 THINKING" if u_context.get("is_processing") else "🟢 READY"
        st.markdown(f"### Status: `{status}`")
    with c3:
        load = u_context.get("system_load", {"cpu": 0, "ram": 0})
        st.caption(f"⚡ CPU: {load['cpu']}% | RAM: {load['ram']}%")
    with c4:
        if st.button("💀 GLOBAL KILL", type="primary", use_container_width=True):
            kill_all_agents()

st.divider()

# Sidebar: Latency Monitor
st.sidebar.title("🩺 Latency Monitor")
last_msg_ts = 0
if latest_job:
    history_file = latest_job / "state" / "chat_history.jsonl"
    if history_file.exists():
        try:
            lines = history_file.read_text(encoding="utf-8-sig").splitlines()
            if lines:
                last_msg = json.loads(lines[-1])
                if last_msg["role"] == "Commander":
                    last_msg_ts = last_msg["ts"]
        except: pass

if last_msg_ts > 0 and u_context.get("is_processing"):
    latency = time.time() - last_msg_ts
    st.sidebar.metric("Deputy Thinking Time", f"{int(latency)}s")
    if latency > 30:
        st.sidebar.error("⚠️ CPU STRESS WARNING: High Inference Latency detected.")
    elif latency > 15:
        st.sidebar.warning("🕒 Hardware Handshake in progress...")
else:
    st.sidebar.info("System Responsive.")

# Tab Navigation
tab_tactical, tab_neural, tab_foundry, tab_logs, tab_system = st.tabs([
    "🎯 Tactical Command", "🧠 Neural Link", "🏗️ Agent Foundry", "📊 Fleet Logs", "⚙️ System Ops"
])

# --- TAB: TACTICAL ---
with tab_tactical:
    col_chat, col_gov = st.columns([3, 1])
    
    with col_chat:
        if not latest_job:
            st.info("No active mission. Commander, state your objective to begin.")
        else:
            history_file = latest_job / "state" / "chat_history.jsonl"
            if history_file.exists():
                messages = []
                with open(history_file, "r", encoding="utf-8") as f:
                    for line in f:
                        try: messages.append(json.loads(line))
                        except: pass
                
                for msg in messages:
                    role = "user" if msg["role"] == "Commander" else "assistant"
                    with st.chat_message(role):
                        st.markdown(msg["content"])
            
            if u_context.get("is_processing"):
                with st.chat_message("assistant"):
                    last_msg_text = ""
                    if history_file.exists():
                        try:
                            lines = history_file.read_text(encoding="utf-8-sig").splitlines()
                            for line in reversed(lines):
                                m = json.loads(line)
                                if m.get("role") == "Commander" and not m.get("processed", False):
                                    last_msg_text = f"Analyzing: *\"{m.get('content')[:100]}...\"*"
                                    break
                        except: pass
                    st.write(f"Chief of Staff is formulating strategy... {last_msg_text}")
                    st.spinner()

    with col_gov:
        st.subheader("🛡️ Governance")
        if latest_job:
            brief_path = latest_job / "state" / "consolidated_brief.md"
            dec_path = latest_job / "state" / "decision.json"
            if brief_path.exists() and not dec_path.exists():
                st.warning("Decision Required")
                st.markdown(brief_path.read_text(encoding="utf-8"))
                if st.button("✅ APPROVE", use_container_width=True):
                    dec_path.write_text(json.dumps({"action": "PROCEED"}))
                    st.rerun()
                if st.button("🚫 VETO", use_container_width=True):
                    dec_path.write_text(json.dumps({"action": "VETO"}))
                    st.rerun()
            else:
                st.success("Policies Enforced")
                st.caption("Awaiting next strategic decision point.")

    # Chat Input
    if prompt := st.chat_input("State mission objective..."):
        if not latest_job:
            subprocess.Popen(["powershell.exe", "-File", "scripts/gemini_orchestrator.ps1", "-Prompt", prompt, "-RepoRoot", str(REPO_ROOT)], creationflags=subprocess.CREATE_NEW_CONSOLE)
            st.toast("Mission Launched!", icon="🚀")
            time.sleep(2)
            st.rerun()
        else:
            send_chat_message(prompt)
            st.rerun()

# --- TAB: NEURAL ---
with tab_neural:
    st.subheader("🧠 Tactical Memory & Context")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("### 📝 Recent Lessons")
        if LESSONS_PATH.exists():
            st.markdown(LESSONS_PATH.read_text(encoding="utf-8"))
    with c2:
        st.markdown("### 🌐 Universal Context")
        st.json(u_context)

# --- TAB: FOUNDRY ---
with tab_foundry:
    st.subheader("🏗️ Strike Team Management")
    if latest_job:
        report_path = latest_job / "learning-summary.json"
        if report_path.exists():
            try:
                report = json.loads(report_path.read_text(encoding="utf-8"))
                st.metric("Avg Mission Score", f"{report.get('avg_score', 0)}/10")
                
                # Score Chart
                df = pd.DataFrame(report.get("agent_scores", []))
                if not df.empty:
                    st.bar_chart(df, x="agent_id", y="score")
            except: pass
    
    st.markdown("---")
    st.markdown("### 📚 Role Library")
    roles_dir = REPO_ROOT / "agents/roles"
    roles = [f.stem for f in roles_dir.glob("*.md")]
    st.write(", ".join([f"`{r}`" for r in roles]))

# --- TAB: LOGS ---
with tab_logs:
    st.subheader("📊 Operational Audit Trail")
    ledger_data = get_ledger()
    if ledger_data:
        df_ledger = pd.DataFrame(ledger_data)
        st.dataframe(df_ledger.tail(50), use_container_width=True)
    
    with st.expander("📂 Raw Specialist Output", expanded=False):
        if latest_job:
            logs = list(latest_job.glob("*.log"))
            for l in logs:
                st.text(f"--- {l.name} ---")
                st.code(l.read_text(encoding="utf-8", errors="ignore")[-2000:])

# --- TAB: SYSTEM ---
with tab_system:
    st.subheader("⚙️ Global Configuration")
    col1, col2 = st.columns(2)
    with col1:
        st.toggle("Autonomous Spawning", value=True, help="Allow Deputy to trigger Foundry")
        st.slider("Min Acceptance Score", 0, 10, 7)
        if st.button("☢️ NUCLEAR RESET", type="primary", use_container_width=True, help="Stop all processes and restart core daemons"):
            nuclear_reset()
    with col2:
        st.selectbox("Default Specialist Model", ["gemini-2.0-flash-exp", "gemini-1.5-pro"])
        st.selectbox("Deputy Inference Model", ["phi3:mini", "phi4"])

# Auto-Refresh
time.sleep(5)
st.rerun()
