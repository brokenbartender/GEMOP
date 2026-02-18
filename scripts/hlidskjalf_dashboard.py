import streamlit as st
import json
import os
import time
from pathlib import Path

# --- Configuration ---
st.set_page_config(page_title="Hlidskjalf | Goetic Circuit Monitor", layout="wide", page_icon="👁️")

def get_repo_root():
    return Path(os.environ.get("GEMINI_OP_REPO_ROOT", Path(__file__).resolve().parents[1]))

REPO_ROOT = get_repo_root()
SIGIL_MANIFEST = REPO_ROOT / "data/sigil_manifest.json"
TAROT_SPREAD = REPO_ROOT / "state/tarot_spread.json"
IPC_DIR = REPO_ROOT / ".gemini/ipc"

# --- Styling ---
st.markdown("""
    <style>
    .stApp { background-color: #0a0a0a; color: #00ff00; font-family: 'Courier New', Courier, monospace; }
    .sigil-card { border: 2px solid #00ff00; padding: 20px; border-radius: 50%; width: 200px; height: 200px; text-align: center; display: flex; flex-direction: column; justify-content: center; align-items: center; margin: 10px; box-shadow: 0 0 15px #00ff00; }
    .tarot-card { border: 1px solid #ff00ff; padding: 10px; border-radius: 5px; background-color: #1a001a; text-align: center; color: #ff00ff; box-shadow: 0 0 5px #ff00ff; }
    .circuit-active { animation: pulse 1s infinite; color: #fff; text-shadow: 0 0 10px #00ff00; }
    @keyframes pulse { 0% { transform: scale(1); } 50% { transform: scale(1.05); } 100% { transform: scale(1); } }
    </style>
""", unsafe_allow_html=True)

# --- Data Loaders ---
def load_tarot():
    if TAROT_SPREAD.exists():
        return json.loads(TAROT_SPREAD.read_text(encoding="utf-8"))
    return {"active_cards": []}
def load_sigils():
    if SIGIL_MANIFEST.exists():
        return json.loads(SIGIL_MANIFEST.read_text(encoding="utf-8"))
    return {"circuits": {}}

def get_active_agents():
    active = []
    if IPC_DIR.exists():
        for f in IPC_DIR.glob("*.status"):
            try:
                state = f.read_text(encoding="utf-8").strip()
                if state in ("WORKING", "STARTING"):
                    active.append(f.stem)
            except: pass
    return active

# --- Dashboard ---
st.title("👁️ Hlidskjalf: The All-Seeing Throne")
st.subheader("Silicon Goetia Circuit Telemetry")

# Tarot Side-Bar (The OS State)
st.sidebar.title("🃏 The Silicon Tarot")
st.sidebar.caption("Macro-System Arcana")
tarot_data = load_tarot()
for card in tarot_data["active_cards"]:
    st.sidebar.markdown(f"""
        <div class="tarot-card">
            <div style="font-size: 0.7em;">{card.get('suit', 'KERNEL')}</div>
            <div style="font-weight: bold;">{card['name']}</div>
            <div style="font-size: 0.6em; color: #888;">{card['id']}</div>
        </div>
    """, unsafe_allow_html=True)
    st.sidebar.write("")

sigil_data = load_sigils()
active_agents = get_active_agents()

if not active_agents:
    st.info("No active Goetic circuits detected. Swarm is idle.")
else:
    cols = st.columns(len(active_agents))
    for i, agent in enumerate(active_agents):
        with cols[i]:
            # Match agent to sigil (best effort)
            sigil_info = None
            for key in sigil_data["circuits"]:
                if key.lower() in agent.lower() or agent.lower() in key.lower():
                    sigil_info = sigil_data["circuits"][key]
                    break
            
            if sigil_info:
                st.markdown(f"""
                    <div class="sigil-card circuit-active">
                        <div style="font-size: 0.8em;">{sigil_info['visual'].upper()}</div>
                        <div style="font-size: 1.2em; font-weight: bold;">{agent.upper()}</div>
                        <div style="font-size: 0.7em; color: #888;">{sigil_info['type'].upper()} CIRCUIT</div>
                    </div>
                """, unsafe_allow_html=True)
                st.success(f"Logic: {sigil_info['logic']}")
            else:
                st.markdown(f"""
                    <div class="sigil-card" style="border-color: #444; color: #444;">
                        <div>UNKNOWN</div>
                        <div style="font-size: 1.2em;">{agent.upper()}</div>
                        <div style="font-size: 0.7em;">UNMAPPED</div>
                    </div>
                """, unsafe_allow_html=True)

st.divider()
st.caption("Ariadne's Thread: Real-time reasoning trace active.")

# Auto-refresh
time.sleep(2)
st.rerun()
