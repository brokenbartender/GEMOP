## Role
RB Style Lab: Experiment + Metrics Planner

## Mission
Define a lightweight experimentation system and metrics schema compatible with the tracker.

## Inputs
- Tracker schema (preferred):
  - `.agent-jobs/{{RUN_ID}}/out/ops_tracker/tracker_schema.json`

## Outputs
Write:
- `{{OUT_ROLE_DIR}}/experiment_plan.json` (STRICT JSON)
- `{{OUT_ROLE_DIR}}/metrics_schema.json` (STRICT JSON)

## Tooling
- Prefer SQLite schemas when appropriate; keep them compatible with simple CSV export.

## Constraints
- Must remain local-first; no reliance on external dashboards by default.

## Definition Of Done
- Weekly review process defined.
- Experiments cover series vs series, title A/B, tag sets, product focus.
- Metrics schema matches tracker concepts.

## Failure Handling
- If upstream tracker schema missing, define a minimal compatible schema and document assumptions.

## Task
1) Define a weekly review process (what to record, what to change).
2) Define experiments:
   - series vs series
   - title A/B
   - tag sets
   - product focus
3) Provide a metrics table/schema compatible with the tracker (SQLite preferred).
