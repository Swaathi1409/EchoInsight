"""Synthetic agent/team assignment. hash(conversation_id) % 25 -> agent."""
from __future__ import annotations

import hashlib

from backend.domain_model import AGENTS_PER_TEAM, NUM_AGENTS, NUM_TEAMS


def assign(conversation_id: str) -> tuple[str, str]:
    """Return (agent_id, team_id) for a conversation. Deterministic."""
    h = int(hashlib.sha256(conversation_id.encode()).hexdigest(), 16)
    agent_idx = h % NUM_AGENTS
    team_idx = agent_idx // AGENTS_PER_TEAM
    return f"agent_{agent_idx:02d}", f"team_{team_idx:02d}"


AGENT_NAMES = {
    f"agent_{i:02d}": f"Agent {i+1:02d}" for i in range(NUM_AGENTS)
}
TEAM_NAMES = {
    f"team_{i:02d}": f"Team {chr(65+i)}" for i in range(NUM_TEAMS)
}
