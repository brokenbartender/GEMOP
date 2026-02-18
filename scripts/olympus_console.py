import streamlit as st
import json
import os
import time
import psutil
from pathlib import Path
import plotly.graph_objects as go

# --- Configuration & Architecture ---
st.set_page_config(page_title="OLYMPUS | Command Console", layout="wide", page_icon="🔱")

def get_repo_root():
    return Path(os.environ.get("GEMINI_OP_REPO_ROOT", Path(__file__).resolve().parents[1]))

REPO_ROOT = get_repo_root()
TAROT_SPREAD = REPO_ROOT / "state/tarot_spread.json"
SIGIL_MANIFEST = REPO_ROOT / "data/sigil_manifest.json"
WAMPUM_LEDGER = REPO_ROOT / "ramshare/state/wampum.jsonl" # Mock path for viz

# --- Custom Style: Cyber-Mythic ---
st.markdown("""
    <style>
    .stApp { background-color: #050505; color: #d4af37; font-family: 'serif'; }
    .cerberus-gate { border: 2px solid #8b0000; padding: 15px; border-radius: 10px; background: rgba(139,0,0,0.1); }
    .hydra-node { border: 2px solid #d4af37; padding: 10px; border-radius: 50%; text-align: center; box-shadow: 0 0 10px #d4af37; }
    .augean-flow { border-left: 3px solid #00ced1; padding-left: 20px; color: #e0e0e0; }
    .titan-toggle { font-size: 2em; font-weight: bold; color: #ff4500; }
    .tarot-card { border: 1px solid #ff00ff; padding: 5px; border-radius: 5px; background: #1a001a; margin-bottom: 5px; }
    </style>
""", unsafe_allow_html=True)

# --- Components ---

def draw_hydra_graph():
    """Visualizes the Hydra Process Tree / Goetia Swarm."""
    # Placeholder for a real node-link graph (e.g., using Graphviz or Plotly)
    fig = go.Figure(go.Scatter(
        x=[0, 1, 2, 1, 0], y=[0, 1, 0, -1, 0],
        mode='markers+text',
        marker=dict(size=[40, 60, 40, 40, 40], color=['#d4af37', '#fff', '#d4af37', '#d4af37', '#d4af37']),
        text=["Bael", "PAIMON", "Valefor", "Phenex", "Gusion"],
        textposition="top center"
    ))
    fig.update_layout(title="The Hydra: Active Goetic Swarm", showlegend=False, 
                      paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                      xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                      yaxis=dict(showgrid=False, zeroline=False, showticklabels=False))
    st.plotly_chart(fig, use_container_width=True)

# --- Layout ---

# Top Bar: The Atlas Toggle
with st.container():
    c1, c2, c3 = st.columns([1, 4, 1])
    with c1:
        st.markdown("<div class='titan-toggle'>🔱 OLYMPUS</div>", unsafe_allow_html=True)
    with c2:
        mode = st.toggle("MORTAL (Local) <---> TITAN (Cloud)", value=True)
        st.caption("Current Strategy: " + ("Shouldering the Sky (Super-Compute)" if mode else "Heroic Endurance (Local Intelligence)"))
    with c3:
        if st.button("💀 GLOBAL CAUTERIZE", type="primary"):
            (REPO_ROOT / "STOP_ALL_AGENTS.flag").touch()

st.divider()

# Triptych Main Layout
left, center, right = st.columns([1, 2, 1])

# 1. LEFT: The Call to Adventure (Strategy)
with left:
    st.header("Cerberus Gate")
    with st.container():
        st.markdown("<div class='cerberus-gate'>", unsafe_allow_html=True)
        st.selectbox("Head 1: Active Memory (Ariadne)", ["Default", "Enterprise Legal", "GEMOP Core"])
        st.text_area("Head 2: Command (The Will)", placeholder="Enter your mission...")
        st.markdown("Head 3: Predictive Cost: **$0.42 (Orichalcum)**", unsafe_allow_html=True)
        if st.button("🔱 SUMMON HEROES"):
            st.success("The Call has been sent.")
        st.markdown("</div>", unsafe_allow_html=True)
    
    st.divider()
    st.subheader("Hippolyta's Keyring")
    st.checkbox("Stripe API (The Girdle)", value=True)
    st.checkbox("GitHub Integration", value=True)
    st.checkbox("Filesystem Access", value=True)

# 2. CENTER: The Battlefield (Execution)
with center:
    st.header("The Battlefield")
    draw_hydra_graph()
    
    with st.expander("Erymanthian Snow Zone (Sandbox)", expanded=True):
        st.code("""# Isolated execution in Buer Container...
import os
print(os.listdir('./work'))
>>> ['Enterprise_Legal_Target']""", language="python")
        st.button("❄️ RELEASE BOAR (Approve Code)")

# 3. RIGHT: The Treasures (Analytics)
with right:
    st.header("The Treasures")
    
    st.subheader("The Silicon Tarot")
    # Load and display real telemetry
    if TAROT_SPREAD.exists():
        tarot = json.loads(TAROT_SPREAD.read_text(encoding="utf-8"))
        for card in tarot.get("active_cards", []):
            st.markdown(f"""
                <div class="tarot-card">
                    <div style="font-size: 0.8em; color: #ff00ff;">{card['suit']}</div>
                    <b>{card['name']}</b>
                </div>
            """, unsafe_allow_html=True)
    
    st.divider()
    st.subheader("Augean Flow")
    st.markdown("""
    <div class="augean-flow">
    <b>[13:42]</b> SLAF_Core.py initialized.<br>
    <b>[13:43]</b> Citations verified (Cerberus).<br>
    <b>[13:45]</b> Code Pushed (Yeet).
    </div>
    """, unsafe_allow_html=True)
    st.slider("Scrub the River (History)", 0, 100, 100)

# --- Footer: The Djed Pillar ---
st.divider()
st.caption("Djed Pillar Status: STABLE | Wampum Treaties: 14 Signed | Signet: READY")

# Auto-refresh logic
time.sleep(5)
st.rerun()
