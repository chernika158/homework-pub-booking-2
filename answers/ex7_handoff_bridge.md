# Ex7 — Handoff bridge

## Your answer

The bridge runs the loop half first, then hands off to the structured half. If the structured half rejects the booking. So for example
 because the party is too large, so the bridge builds a new task 
 that includes the rejection reason and runs the loop again. In my run it took 2 rounds: the first venue got rejected, the second was confirmed.

## Citations

- sessions/sess_e7e2e85b0291/logs/trace.jsonl:14 — forward handoff event (from: loop, to: structured)
- sessions/sess_e7e2e85b0291/logs/trace.jsonl:17 — structured half rejection and reverse handoff (from: structured, to: loop, rejection_reason: party_too_large)
- sessions/sess_e7e2e85b0291/logs/trace.jsonl:21 — reverse handoff triggers Round 2 (bridge.round_start for round 2)