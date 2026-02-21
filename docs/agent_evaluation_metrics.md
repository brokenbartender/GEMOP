# Agent Evaluation Metrics and Guidelines

As of 2026, robust AI evaluation is mission-critical for production LLM applications [1]. This document outlines the evaluation metrics and guidelines for agents operating within the `gemini-op-clean` repository to ensure quality and reliability.

## 1. Output Contract Adherence
Agents must strictly adhere to their defined output contracts (e.g., `DECISION_JSON` schema, markdown formatting).
- **Metric**: Percentage of outputs conforming to schema.
- **Failure Mode**: Malformed JSON, missing required fields, incorrect data types, `DECISION_JSON` block missing or unparseable.

## 2. Grounding and Citation Accuracy
All factual claims made by agents must be grounded in provided evidence (e.g., file contents, web search results) and correctly cited. Citations should explicitly refer to repo files when applicable.
- **Metric**: Ratio of factual claims with valid citations to total factual claims. Evaluation includes checking if cited files exist and content supports the claim.
- **Failure Mode**: Hallucinations, incorrect citations, unsupported claims, referring to non-existent files or irrelevant content.

## 3. Actionability and Minimality of Changes
Proposed repo changes (patches) must be actionable, minimal, and high-leverage, as per mission constraints.
- **Metric**: Manual review of diffs for adherence to file path constraints (`scripts/`, `docs/`, `config/`, `mcp/`).
- **Failure Mode**: Changes outside allowed directories, excessive modifications, non-unified diffs.

## 4. Verification Command Efficacy
Verification commands must be deterministic and effectively validate the proposed changes.
- **Metric**: Success rate of verification commands.
- **Failure Mode**: Non-deterministic commands, commands that don't verify the change, missing commands.

## 5. Refusal and Injection Resilience
Agents should handle adversarial inputs gracefully, refusing inappropriate requests and resisting prompt injection attempts.
- **Metric**: Count of `refusal_hits` and `injection_hits` (from `WORLD STATE` metrics).
- **Failure Mode**: Execution of harmful instructions, divulging sensitive information.

## 6. Efficiency and Resource Usage
Agents should operate efficiently, minimizing token usage and processing time.
- **Metric**: Token count per turn, processing time.
- **Failure Mode**: Excessive token use, slow response times.

**Reference**:
- [1] `https://www.getmaxim.ai/articles/best-ai-evaluation-tools-in-2026-top-5-picks/`
