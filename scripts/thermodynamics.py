import argparse
import json
import math
import time
from pathlib import Path
import os

# Physical Constants (Simulated for AI Context)
K_B = 0.7  # Boltzmann Constant (Base System Temperature)
T = 300    # Absolute Temperature (Volatility)
LN2 = math.log(2)

def calculate_entropy(microstates: int) -> float:
    """
    S = k * ln(Omega)
    Measures 'Confusion' in the context.
    """
    if microstates <= 0:
        return 0.0
    return K_B * math.log(microstates)

def calculate_lyapunov(initial_error: float, rate: float, rounds: int) -> float:
    """
    delta(t) = delta_0 * e^(lambda * t)
    Measures 'Divergence' (Hallucination Horizon).
    """
    return initial_error * math.exp(rate * rounds)

def calculate_landauer_cost(bits_erased: int) -> float:
    """
    E = k * T * ln(2)
    Measures 'Cost of Forgetting' per bit.
    """
    return bits_erased * K_B * T * LN2

class Thermodynamics:
    def __init__(self, run_dir: Path):
        self.run_dir = run_dir
        self.state_dir = run_dir / "state"
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.thermo_log = self.state_dir / "thermodynamics.json"

    def update_state(self, metrics: dict):
        current_state = {}
        if self.thermo_log.exists():
            try:
                current_state = json.loads(self.thermo_log.read_text(encoding='utf-8'))
            except:
                pass
        
        current_state.update(metrics)
        current_state["last_update"] = time.time()
        self.thermo_log.write_text(json.dumps(current_state, indent=2), encoding='utf-8')

    def monitor_entropy(self, round_num: int, agent_responses: list):
        """
        Calculates Entropy based on response variance.
        If S > Threshold, recommends 'Maxwell's Demon' compression.
        """
        # Omega = Number of unique semantic blocks or variance measure
        # Simplified: unique word count ratio or response length variance
        if not agent_responses:
            return 0.0
        
        # Simple Omega: Number of distinct responses if we were looking for consensus
        # Here we'll simulate Omega based on the 'branching' of ideas
        omega = len(set(agent_responses)) + 1 
        entropy = calculate_entropy(omega)
        
        print(f"[Entropy] Round {round_num}: S = {entropy:.4f} (Omega={omega})")
        
        if entropy > 1.2: # Critical mass threshold
            print("[Maxwell] CRITICAL ENTROPY. Venting heat via context compression.")
            return "compress"
        return "stable"

    def monitor_lyapunov(self, round_num: int, semantic_distance: float):
        """
        Predicts divergence. If delta(t) approaches horizon, recommend cauterization.
        """
        # Lambda (rate) simulated as increasing with round depth if not grounded
        rate = 0.5 
        delta_t = calculate_lyapunov(semantic_distance, rate, round_num)
        
        print(f"[Lyapunov] Round {round_num}: Delta(t) = {delta_t:.4f}")
        
        if delta_t > 50.0: # Hallucination Horizon
            print("[Iolaus] HALLUCINATION HORIZON REACHED. Exponential divergence detected.")
            return "kill"
        return "stable"

    def fluid_router(self, queue_depth: int, task_complexity: float):
        """
        Navier-Stokes: Manages laminar vs turbulent data flow.
        """
        # Simplified Reynolds Number calculation: Re = (velocity * length) / viscosity
        # velocity = tokens/sec (simulated)
        # viscosity = task_complexity
        velocity = 100.0 / (queue_depth + 1)
        reynolds = (velocity * 10.0) / (task_complexity + 0.1)
        
        print(f"[Navier] Reynolds Number: {reynolds:.2f} (u={velocity:.2f}, nu={task_complexity:.2f})")
        
        if reynolds > 2000: # Turbulence threshold
            print("[Navier] TURBULENCE DETECTED. Throttling background velocity.")
            return "throttle"
        return "laminar"

    def landauer_ledger(self, tokens_to_prune: int):
        """
        Calculates if the cost of erasing is higher than the cost of keeping.
        """
        erasure_energy = calculate_landauer_cost(tokens_to_prune)
        retention_cost = tokens_to_prune * 0.01 # Simulated token cost for keeping
        
        print(f"[Landauer] Erasure Energy: {erasure_energy:.2f} vs Retention Cost: {retention_cost:.2f}")
        
        if erasure_energy > retention_cost:
            print("[Landauer] KEEP CONTEXT. Erasure dissipates too much latent link energy.")
            return "keep"
        return "prune"

def main():
    parser = argparse.ArgumentParser(description="Thermodynamics of Intelligence State Monitor.")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--mode", choices=["entropy", "lyapunov", "navier", "landauer"], required=True)
    parser.add_argument("--round", type=int, default=1)
    parser.add_argument("--val", type=float, default=0.0)
    parser.add_argument("--tokens", type=int, default=0)
    parser.add_argument("--queue", type=int, default=0)
    args = parser.parse_args()

    thermo = Thermodynamics(Path(args.run_dir))
    
    if args.mode == "entropy":
        # Simulating agent responses for CLI testing
        res = thermo.monitor_entropy(args.round, ["res1", "res2", "res3"] if args.val > 0 else ["res1"])
        print(res)
    elif args.mode == "lyapunov":
        res = thermo.monitor_lyapunov(args.round, args.val)
        print(res)
    elif args.mode == "navier":
        res = thermo.fluid_router(args.queue, args.val)
        print(res)
    elif args.mode == "landauer":
        res = thermo.landauer_ledger(args.tokens)
        print(res)

if __name__ == "__main__":
    main()
