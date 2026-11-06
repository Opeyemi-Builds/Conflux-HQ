"""AI layer (owner: Adekola Folarin John).

Planned modules:
  classifier.py  complaint text -> issue_type, severity, sentiment, language, amount
  agent.py       investigation agent with tools (incident stats, transactions, events)
  drafts.py      customer holding message and IT ticket drafts

Contract with the backend: write classification results with
PATCH /api/v1/complaints/{id}/classification, and write drafts to the `drafts`
table with status "pending". The agent proposes; a human approves.
"""
