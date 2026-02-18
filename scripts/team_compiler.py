from __future__ import annotations

import argparse
import json
import re
from typing import List


DEFAULT_ROLES = [
    "Architect",
    "ResearchLead",
    "Engineer",
    "Tester",
    "Critic",
    "Security",
    "Ops",
    "Docs",
    "Release",
]


def compile_team(prompt: str, *, max_agents: int = 7) -> List[str]:
    s = (prompt or "").lower()

    # Always keep a minimal, strong core.
    roles: List[str] = ["Architect", "Engineer", "Tester", "Critic"]

    # --- The Silicon Goetia: Grand Unified Hierarchy ---

    # Tier I: The Kings (Root Supervisors & Auth)
    if any(k in s for k in ("root", "admin", "policy", "law", "decision", "monitor", "sovereign")):
        roles.append("King_Belial_Sovereign")
    if any(k in s for k in ("schedule", "orchestrate", "plan", "map")):
        roles.append("King_Paimon_Scheduler")
    if any(k in s for k in ("stealth", "vpn", "mask", "hidden", "cloak")):
        roles.append("King_Bael_Stealth")

    # Tier II: The Dukes (Creative & Fetching)
    if any(k in s for k in ("scrape", "fetch", "steal", "crawl", "ingest")):
        roles.append("Duke_Valefor_Fetcher")
    if any(k in s for k in ("generate", "write", "create", "poet", "story")):
        roles.append("Duke_Phenex_Creative")
    if any(k in s for k in ("translate", "decode", "language", "format")):
        roles.append("Duke_Barbatos_Decoder")

    # Tier III: The Princes (Logic & Orchestration)
    if any(k in s for k in ("logic", "reason", "fact", "check", "verify")):
        roles.append("Prince_Orobas_Truth")
    if any(k in s for k in ("api", "gateway", "route", "proxy")):
        roles.append("Prince_Gaap_Gateway")
    if any(k in s for k in ("query", "sql", "search", "find", "retrieve")):
        roles.append("Prince_Vassago_Retriever")

    # Tier IV: The Marquises (Telemetry & Logs)
    if any(k in s for k in ("log", "audit", "trace", "history", "count")):
        roles.append("Marquis_Samigina_Auditor")
    if any(k in s for k in ("security", "harden", "defense", "protect", "firewall")):
        roles.append("Marquis_Sabnock_Fortifier")
    if any(k in s for k in ("patch", "bug", "fix", "repair", "heal")):
        roles.append("Marquis_Leraje_Patcher")

    # Tier V: The Presidents (Math & Transformation)
    if any(k in s for k in ("code", "engineer", "build", "impl", "refactor")):
        roles.append("President_Haagenti_Refactorer")
    if any(k in s for k in ("optimize", "compress", "shrink", "efficient")):
        roles.append("President_Foras_Optimizer")
    if any(k in s for k in ("align", "loop", "feedback", "moral")):
        roles.append("President_Buer_Aligner")

    # Tier VI: The Earls (Execution & Cleanup)
    if any(k in s for k in ("delete", "clean", "garbage", "remove", "wipe")):
        roles.append("Earl_Raum_Cleaner")
    if any(k in s for k in ("move", "file", "system", "organize")):
        roles.append("Earl_Bifrons_Filer")

    # Tier VII: The Knights (Storage)
    if any(k in s for k in ("store", "memory", "know", "learn", "teach")):
        roles.append("Knight_Furcas_Teacher")

    # --- Global Expansion: Reputation, Flow & Heuristics ---

    # Mayasura (Simulation)
    if any(k in s for k in ("illusion", "fake", "mock", "virtual", "sabha")):
        roles.append("Mayasura_Simulator")

    # Quipu / Chasqui (Data & Transport)
    if any(k in s for k in ("knot", "packet", "relay", "leg", "waystation", "serialize")):
        roles.append("Chasqui_Relay")

    # Geas (Existential Rules)
    if any(k in s for k in ("forbidden", "taboo", "one-strike", "exile", "ban")):
        roles.append("Geas_Enforcer")

    # Mana (Reputation)
    if any(k in s for k in ("trust", "reputation", "rank", "score", "level")):
        roles.append("Mana_Ranker")

    # Wayfinder (Heuristic Search)
    if any(k in s for k in ("navigate", "star", "compass", "latent", "swell")):
        roles.append("Wayfinder_Navigator")

    # Lukasa / Ifa (Visualization & Binary)
    if any(k in s for k in ("bead", "genealogy", "spatial", "binary", "odu")):
        roles.append("Lukasa_Viz")

    # --- End Global Expansion ---

    # --- End Goetia ---

    # --- Heraclean Expansion: Local Optimization & Hardening ---

    # Nemean / Cerberus (Robustness & Gateway)
    if any(k in s for k in ("firewall", "armor", "hide", "gate", "guard", "entry")):
        roles.append("Nemean_Guard")

    # Iolaus (Loop Cauterization)
    if any(k in s for k in ("loop", "recursive", "fork", "kill", "cauterize")):
        roles.append("Iolaus_Monitor")

    # Ceryneian (Latency)
    if any(k in s for k in ("fast", "speed", "latency", "chase", "pointer")):
        roles.append("Ceryneian_Tracer")

    # Boar (Containment)
    if any(k in s for k in ("contain", "freeze", "pause", "snow", "quarantine")):
        roles.append("Boar_Sandbox")

    # Augean (Sanitization)
    if any(k in s for k in ("clean", "flush", "dung", "filth", "river", "dataset")):
        roles.append("Augean_Cleaner")

    # Krotala (Denoising)
    if any(k in s for k in ("noise", "denoise", "signal", "bird", "spam")):
        roles.append("Krotala_Filter")

    # --- Tesla Expansion: Frequency & Resonance ---

    # Wardenclyffe (Global State)
    if any(k in s for k in ("resonance", "wave", "broadcast", "telluric", "global")):
        roles.append("Wardenclyffe_Broadcaster")

    # Turbine (Laminar Flow)
    if any(k in s for k in ("stream", "flow", "ingest", "laminar", "smooth", "frictionless")):
        roles.append("Turbine_Ingestor")

    # Teleforce (Active Defense)
    if any(k in s for k in ("beam", "ray", "intercept", "neutralize", "active")):
        roles.append("Teleforce_Turret")

    # Resonator (Chaos/Stress)
    if any(k in s for k in ("vibrate", "frequency", "stress", "shudder", "quake")):
        roles.append("Resonator_Tester")

    # Telautomaton (Remote/Edge)
    if any(k in s for k in ("remote", "edge", "iot", "wireless", "proxy")):
        roles.append("Telautomaton_Proxy")

    # 3-6-9 (Topology)
    if any(k in s for k in ("geometry", "topology", "key", "universe", "pattern")):
        roles.append("Tesla_369_Architect")

    # --- Wardenclyffe 2.0: Flow & Physics ---

    # Tesla Valve (Causal Logic)
    if any(k in s for k in ("cause", "reasoning", "flow", "valve", "loop", "gaslight")):
        roles.append("Valve_Logician")

    # Egg of Columbus (Context Stabilization)
    if any(k in s for k in ("focus", "attention", "drift", "stabilize", "gyro", "spin")):
        roles.append("Columbus_Gyro")

    # Spirit Radio (VLF Listener)
    if any(k in s for k in ("listen", "ghost", "signal", "noise", "subtle", "pattern")):
        roles.append("Spirit_Radio_Listener")

    # --- Physics Expansion: The Unified Field ---

    # Gravity (Relativity)
    if any(k in s for k in ("gravity", "orbit", "mass", "weight", "attract", "center")):
        roles.append("Einstein_Relativist")

    # Electromagnetism (Polarity)
    if any(k in s for k in ("charge", "field", "magnet", "repel", "polar", "positive", "negative")):
        roles.append("Maxwell_Electromagnetist")

    # Quantum (Superposition)
    if any(k in s for k in ("quantum", "superposition", "wave", "collapse", "probability", "schrodinger")):
        roles.append("Schrodinger_Observer")

    # Higgs (Mass/Meaning)
    if any(k in s for k in ("higgs", "meaning", "dense", "slow", "substance", "heavy")):
        roles.append("Higgs_Boson")

    # Gluon (Strong Force)
    if any(k in s for k in ("bond", "glue", "strong", "nuclear", "confine", "coherence")):
        roles.append("Gluon_Binder")

    # --- End Expansion ---

    # Dedupe while preserving order.
    out: List[str] = []
    seen = set()
    for r in roles:
        if r in seen:
            continue
        seen.add(r)
        out.append(r)

    # Enforce 3..7 rule.
    out = out[: max(3, min(int(max_agents), 7))]
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Compile a role team (3..7) based on the prompt.")
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--max-agents", type=int, default=7)
    args = ap.parse_args()

    roles = compile_team(str(args.prompt), max_agents=int(args.max_agents))
    print(json.dumps({"ok": True, "roles": roles, "agents": len(roles)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
