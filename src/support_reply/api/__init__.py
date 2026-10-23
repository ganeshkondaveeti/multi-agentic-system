"""HTTP API for Reply Desk. `support_reply.api.app:app` is the ASGI app.

Thin wrappers over `graph.complaint_turn`, `session.refine_turn`, and `gate.approve`.
No agent, reviewer, or gate logic lives here.
"""
