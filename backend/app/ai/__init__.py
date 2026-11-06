"""AI implementation for Conflux HQ.

- classifier.py classifies masked complaints with Claude or deterministic fallback.
- evidence.py builds factual incident evidence from database records.
- agent.py turns evidence into a bounded investigation result.
- drafts.py creates customer and IT drafts, which require human approval.

The AI never executes a reversal or any other money movement.
"""
