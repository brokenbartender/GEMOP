# Lessons Learned (Tactical Memory)

Add short, durable rules here after failures/successes.

Format:
- Date
- Trigger (what happened)
- Lesson (one sentence)
- Action (what to do next time)


- 2026-02-13 | Trigger: council_3_debate-job-20260213-015042-d0dbe691/agent1 score=0 | Lesson: prevent no_structured_rows, insufficient_ranked_rows, missing_contract_headers, missing_final_output_block, missing_completion_marker, missing_repo_context using stricter output contracts | Action: apply model prompt hints and rerun section.
- 2026-02-13 | Trigger: council_3_debate-job-20260213-015042-d0dbe691/agent2 score=0 | Lesson: prevent no_structured_rows, insufficient_ranked_rows, missing_contract_headers, missing_final_output_block, missing_completion_marker, missing_repo_context using stricter output contracts | Action: apply model prompt hints and rerun section.
- 2026-02-13 | Trigger: council_3_debate-job-20260213-015042-d0dbe691/agent3 score=0 | Lesson: prevent no_structured_rows, insufficient_ranked_rows, missing_contract_headers, missing_final_output_block, missing_completion_marker, missing_repo_context using stricter output contracts | Action: apply model prompt hints and rerun section.

- 2026-02-14 | Trigger: job-autonomous-final-20260214-221336/agent1 score=0 | Lesson: prevent missing_output using stricter output contracts | Action: apply model prompt hints and rerun section.
- 2026-02-14 | Trigger: job-autonomous-final-20260214-221336/agent2 score=0 | Lesson: prevent missing_output using stricter output contracts | Action: apply model prompt hints and rerun section.
- 2026-02-14 | Trigger: job-autonomous-final-20260214-221336/agent3 score=0 | Lesson: prevent missing_output using stricter output contracts | Action: apply model prompt hints and rerun section.
- 2026-02-14 | Trigger: job-autonomous-final-20260214-221336/council score=69 | Lesson: prevent council_protocol_not_followed using stricter output contracts | Action: apply model prompt hints and rerun section.

- Council job-autonomous-final-20260214-221336: council_protocol_not_followed observed 1x | Action: enforce manifesto delta and verify via council ack.

- 2026-02-14 | Trigger: job-final-recovery-20260214-221523/agent1 score=0 | Lesson: prevent missing_output using stricter output contracts | Action: apply model prompt hints and rerun section.
- 2026-02-14 | Trigger: job-final-recovery-20260214-221523/agent2 score=0 | Lesson: prevent missing_output using stricter output contracts | Action: apply model prompt hints and rerun section.
- 2026-02-14 | Trigger: job-final-recovery-20260214-221523/agent3 score=0 | Lesson: prevent missing_output using stricter output contracts | Action: apply model prompt hints and rerun section.
- 2026-02-14 | Trigger: job-final-recovery-20260214-221523/council score=69 | Lesson: prevent council_protocol_not_followed using stricter output contracts | Action: apply model prompt hints and rerun section.

- Council job-final-recovery-20260214-221523: council_protocol_not_followed observed 1x | Action: enforce manifesto delta and verify via council ack.

- 2026-02-14 | Trigger: job-CONFIRMED-FINAL-20260214-221729/agent1 score=0 | Lesson: prevent no_structured_rows, insufficient_ranked_rows, missing_contract_headers, missing_final_output_block, missing_file_citations, missing_repo_context using stricter output contracts | Action: apply model prompt hints and rerun section.
- 2026-02-14 | Trigger: job-CONFIRMED-FINAL-20260214-221729/agent2 score=0 | Lesson: prevent no_structured_rows, insufficient_ranked_rows, missing_contract_headers, missing_final_output_block, missing_completion_marker, missing_file_citations, missing_repo_context using stricter output contracts | Action: apply model prompt hints and rerun section.
- 2026-02-14 | Trigger: job-CONFIRMED-FINAL-20260214-221729/agent3 score=0 | Lesson: prevent no_structured_rows, insufficient_ranked_rows, missing_contract_headers, missing_final_output_block, missing_completion_marker, missing_file_citations, missing_repo_context using stricter output contracts | Action: apply model prompt hints and rerun section.

- 2026-02-14 | Trigger: job-FREE-FUSION-20260214-224054/agent1 score=0 | Lesson: prevent no_structured_rows, insufficient_ranked_rows, missing_contract_headers, missing_final_output_block, missing_completion_marker, missing_file_citations, missing_repo_context using stricter output contracts | Action: apply model prompt hints and rerun section.
- 2026-02-14 | Trigger: job-FREE-FUSION-20260214-224054/agent2 score=0 | Lesson: prevent no_structured_rows, insufficient_ranked_rows, missing_contract_headers, missing_final_output_block, missing_file_citations, missing_repo_context using stricter output contracts | Action: apply model prompt hints and rerun section.
- 2026-02-14 | Trigger: job-FREE-FUSION-20260214-224054/agent3 score=0 | Lesson: prevent no_structured_rows, insufficient_ranked_rows, missing_contract_headers, missing_final_output_block, missing_completion_marker, missing_file_citations, missing_repo_context using stricter output contracts | Action: apply model prompt hints and rerun section.

- 2026-02-14 | Trigger: job-SUPERCHARGED-20260214-225642/agent1 score=0 | Lesson: prevent no_structured_rows, insufficient_ranked_rows, missing_contract_headers, missing_final_output_block, missing_file_citations, missing_repo_context using stricter output contracts | Action: apply model prompt hints and rerun section.
- 2026-02-14 | Trigger: job-SUPERCHARGED-20260214-225642/agent2 score=0 | Lesson: prevent too_short, no_structured_rows, insufficient_ranked_rows, missing_contract_headers, missing_final_output_block, missing_completion_marker, missing_file_citations, missing_repo_context using stricter output contracts | Action: apply model prompt hints and rerun section.
- 2026-02-14 | Trigger: job-SUPERCHARGED-20260214-225642/agent3 score=0 | Lesson: prevent no_structured_rows, insufficient_ranked_rows, missing_contract_headers, missing_final_output_block, missing_completion_marker, missing_file_citations, missing_repo_context using stricter output contracts | Action: apply model prompt hints and rerun section.

- 2026-02-14 | Trigger: job-SPEED-TUNED-20260214-230518/agent1 score=5 | Lesson: prevent no_structured_rows, insufficient_ranked_rows, missing_contract_headers, missing_file_citations, missing_repo_context using stricter output contracts | Action: apply model prompt hints and rerun section.
- 2026-02-14 | Trigger: job-SPEED-TUNED-20260214-230518/agent2 score=0 | Lesson: prevent no_structured_rows, insufficient_ranked_rows, missing_contract_headers, missing_final_output_block, missing_completion_marker, missing_file_citations, missing_repo_context using stricter output contracts | Action: apply model prompt hints and rerun section.
- 2026-02-14 | Trigger: job-SPEED-TUNED-20260214-230518/agent3 score=0 | Lesson: prevent no_structured_rows, insufficient_ranked_rows, missing_contract_headers, missing_final_output_block, missing_completion_marker, missing_file_citations, missing_repo_context using stricter output contracts | Action: apply model prompt hints and rerun section.

- 2026-02-14 | Trigger: job-TIERED-FINAL-20260214-232513/agent1 score=0 | Lesson: prevent no_structured_rows, insufficient_ranked_rows, missing_contract_headers, missing_final_output_block, missing_file_citations, missing_repo_context using stricter output contracts | Action: apply model prompt hints and rerun section.

- 2026-02-14 | Trigger: job-CLOUD-HANDSHAKE-20260214-232737/agent1 score=0 | Lesson: prevent no_structured_rows, insufficient_ranked_rows, missing_contract_headers, missing_final_output_block, missing_completion_marker, missing_file_citations, missing_repo_context using stricter output contracts | Action: apply model prompt hints and rerun section.

- 2026-02-14 | Trigger: job-DEFINITIVE-CLOUD-20260214-232936/agent1 score=0 | Lesson: prevent no_structured_rows, insufficient_ranked_rows, missing_contract_headers, missing_final_output_block, missing_completion_marker, missing_file_citations, missing_repo_context using stricter output contracts | Action: apply model prompt hints and rerun section.

- 2026-02-14 | Trigger: job-i5-STABLE-20260214-233435/agent1 score=0 | Lesson: prevent no_structured_rows, insufficient_ranked_rows, missing_contract_headers, missing_final_output_block, missing_completion_marker, missing_file_citations, missing_repo_context using stricter output contracts | Action: apply model prompt hints and rerun section.
- 2026-02-14 | Trigger: job-i5-STABLE-20260214-233435/agent2 score=0 | Lesson: prevent no_structured_rows, insufficient_ranked_rows, missing_contract_headers, missing_final_output_block, missing_completion_marker, missing_file_citations, missing_repo_context using stricter output contracts | Action: apply model prompt hints and rerun section.
- 2026-02-14 | Trigger: job-i5-STABLE-20260214-233435/agent3 score=0 | Lesson: prevent no_structured_rows, insufficient_ranked_rows, missing_contract_headers, missing_final_output_block, missing_completion_marker, missing_file_citations, missing_repo_context using stricter output contracts | Action: apply model prompt hints and rerun section.

- 2026-02-14 | Trigger: job-HYPER-FUSION-20260214-234602/agent1 score=0 | Lesson: prevent no_structured_rows, insufficient_ranked_rows, missing_contract_headers, missing_final_output_block, missing_completion_marker, missing_file_citations, missing_repo_context using stricter output contracts | Action: apply model prompt hints and rerun section.

- 2026-02-14 | Trigger: job-VIGILANCE-FINAL-20260214-235415/agent1 score=0 | Lesson: prevent no_structured_rows, insufficient_ranked_rows, missing_contract_headers, missing_final_output_block, missing_completion_marker, missing_file_citations, missing_repo_context using stricter output contracts | Action: apply model prompt hints and rerun section.

- 2026-02-15 | Trigger: job-VIGILANCE-FINAL-20260214-235735/agent1 score=0 | Lesson: prevent no_structured_rows, insufficient_ranked_rows, missing_contract_headers, missing_final_output_block, missing_completion_marker, missing_file_citations, missing_repo_context using stricter output contracts | Action: apply model prompt hints and rerun section.

- 2026-02-15 | Trigger: job-FORGE-CONFIRM-20260215-000244/agent1 score=0 | Lesson: prevent no_structured_rows, insufficient_ranked_rows, missing_contract_headers, missing_final_output_block, missing_completion_marker, missing_file_citations, missing_repo_context using stricter output contracts | Action: apply model prompt hints and rerun section.

- 2026-02-15 | Trigger: job-FORGE-DEFINITIVE-20260215-000548/agent1 score=0 | Lesson: prevent no_structured_rows, insufficient_ranked_rows, missing_contract_headers, missing_final_output_block, missing_completion_marker, missing_file_citations, missing_repo_context using stricter output contracts | Action: apply model prompt hints and rerun section.

- 2026-02-15 | Trigger: job-SOVEREIGN-CONFIRMED-20260215-001432/agent1 score=0 | Lesson: prevent no_structured_rows, insufficient_ranked_rows, missing_contract_headers, missing_final_output_block, missing_completion_marker, missing_file_citations, missing_repo_context using stricter output contracts | Action: apply model prompt hints and rerun section.

- 2026-02-15 | Trigger: job-POST-UPDATE-CANARY-20260215-002618/agent1 score=0 | Lesson: prevent no_structured_rows, insufficient_ranked_rows, missing_contract_headers, missing_final_output_block, missing_completion_marker, missing_file_citations, missing_repo_context using stricter output contracts | Action: apply model prompt hints and rerun section.

- 2026-02-15 | Trigger: job-GROQ-CONFIRMED-20260215-004123/agent1 score=0 | Lesson: prevent no_structured_rows, insufficient_ranked_rows, missing_contract_headers, missing_final_output_block, missing_completion_marker, missing_file_citations, missing_repo_context using stricter output contracts | Action: apply model prompt hints and rerun section.

- 2026-02-15 | Trigger: job-GROQ-PRIORITY-20260215-004350/agent1 score=0 | Lesson: prevent no_structured_rows, insufficient_ranked_rows, missing_contract_headers, missing_final_output_block, missing_file_citations, missing_repo_context using stricter output contracts | Action: apply model prompt hints and rerun section.

- 2026-02-15 | Trigger: job-GROQ-DEFINITIVE-20260215-004616/agent1 score=0 | Lesson: prevent no_structured_rows, insufficient_ranked_rows, missing_contract_headers, missing_final_output_block, missing_file_citations, missing_repo_context using stricter output contracts | Action: apply model prompt hints and rerun section.

- 2026-02-15 | Trigger: job-GROQ-DEFINITIVE-FINAL-20260215-004938/agent1 score=0 | Lesson: prevent no_structured_rows, insufficient_ranked_rows, missing_contract_headers, missing_final_output_block, missing_completion_marker, missing_file_citations, missing_repo_context using stricter output contracts | Action: apply model prompt hints and rerun section.

- 2026-02-15 | Trigger: job-VERTEX-ENABLED-20260215-005418/agent1 score=0 | Lesson: prevent no_structured_rows, insufficient_ranked_rows, missing_contract_headers, missing_final_output_block, missing_completion_marker, missing_file_citations, missing_repo_context using stricter output contracts | Action: apply model prompt hints and rerun section.

- 2026-02-15 | Trigger: job-DUAL-CLOUD-FIX-20260215-005728/agent1 score=0 | Lesson: prevent no_structured_rows, insufficient_ranked_rows, missing_contract_headers, missing_completion_marker, missing_file_citations, missing_repo_context using stricter output contracts | Action: apply model prompt hints and rerun section.

- 2026-02-15 | Trigger: job-SERVICE-ACCOUNT-FINAL-20260215-011147/agent1 score=0 | Lesson: prevent missing_output using stricter output contracts | Action: apply model prompt hints and rerun section.

- 2026-02-15 | Trigger: job-DEFINITIVE-SA-FINAL-20260215-011622/agent1 score=0 | Lesson: prevent missing_output, runtime_exception using stricter output contracts | Action: apply model prompt hints and rerun section.

- 2026-02-15 | Trigger: job-SOVEREIGN-STABLE-20260215-011925/agent1 score=0 | Lesson: prevent missing_output, runtime_exception using stricter output contracts | Action: apply model prompt hints and rerun section.
- 2026-02-15 | Trigger: job-SOVEREIGN-STABLE-20260215-011925/agent2 score=0 | Lesson: prevent missing_output, runtime_exception using stricter output contracts | Action: apply model prompt hints and rerun section.
- 2026-02-15 | Trigger: job-SOVEREIGN-STABLE-20260215-011925/agent3 score=0 | Lesson: prevent missing_output, runtime_exception using stricter output contracts | Action: apply model prompt hints and rerun section.

- 2026-02-15 | Trigger: job-DEFINITIVE-KEY-FINAL-20260215-012724/agent1 score=0 | Lesson: prevent missing_output, runtime_exception using stricter output contracts | Action: apply model prompt hints and rerun section.
