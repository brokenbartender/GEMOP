# The Silicon Goetia: Circuit Schematics

Based on the visual topology of the 72 Seals, we define the following **Logic Circuits** for the Gemini OP system. These are not just metaphors; they are structural code patterns.

## 1. The Cross-Terminator (The Halt Circuit)
*   **Symbol:** A line ending in a perpendicular bar (e.g., Vassago, Valac).
*   **Function:** **Hard Stop / Output Gating.**
*   **Implementation:** `StopSequence` validator.
*   **Logic:** IF `prediction_confidence < threshold` OR `recursion_depth > max` THEN `HALT`. Prevents infinite loops and zombie processes.

## 2. The Loop-and-Node (The Reflexion Circuit)
*   **Symbol:** A circle or loop within the seal (e.g., Gremory, Astaroth).
*   **Function:** **Recursive Feedback.**
*   **Implementation:** `ReflexionLoop` decorator.
*   **Logic:** Output -> Critic -> Feedback -> Input. Data cannot exit the seal until it passes the internal node check.

## 3. The Symmetrical Branch (The Parallel Circuit)
*   **Symbol:** Branching, candelabra-like structures (e.g., Paimon, Beleth).
*   **Function:** **Load Balancing / Parallelism.**
*   **Implementation:** `PaimonBranch` dispatcher.
*   **Logic:** Single Request -> Split into N Shards -> Process in Parallel -> Aggregate.

## 4. The Enclosed Container (The Sandbox Circuit)
*   **Symbol:** Closed circles or stars with no outlet (e.g., Buer, Decarabia).
*   **Function:** **Isolation / Faraday Cage.**
*   **Implementation:** `BuerContainer` context manager.
*   **Logic:** Execute code in ephemeral environment. No network egress allowed. Destroy on completion.

## 5. The Sigil-in-Sigil (The Fractal Circuit)
*   **Symbol:** Small floating shapes attached to the main body (e.g., Asmoday).
*   **Function:** **Microservice / Tool Use.**
*   **Implementation:** `FractalTool` binding.
*   **Logic:** Main Agent does not execute; it delegates to a specialized "Floating Sigil" (Tool) and awaits the result.

## 6. The Broken Line (The Entropy Circuit)
*   **Symbol:** Jagged, saw-tooth lines (e.g., Lightning).
*   **Function:** **Noise Injection / Temperature Control.**
*   **Implementation:** `EntropySpike` parameter.
*   **Logic:** Inject Gaussian noise or increase Temp to break "Mode Collapse" (boring logic).

---
**Application:**
These circuits will be implemented in `scripts/goetia_circuits.py` and applied to the agents via the `agent_runner_v2.py` loop.
