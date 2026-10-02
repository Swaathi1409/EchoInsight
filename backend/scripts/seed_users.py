"""Seed initial users and synthetic agents/teams."""
from __future__ import annotations
import asyncio
import logging
from sqlalchemy import select

from backend.auth import hash_password
from backend.config.settings import get_settings
from backend.db import get_db_session, init_db, create_all_tables
from backend.domain_model import NUM_AGENTS, NUM_TEAMS, AGENTS_PER_TEAM
from backend.ingest.assignment import AGENT_NAMES, TEAM_NAMES
from backend.models import Agent, Team, User

logger = logging.getLogger(__name__)


async def seed() -> None:
    s = get_settings()
    await create_all_tables()

    # Teams
    async with get_db_session() as session:
        for team_id, display_name in TEAM_NAMES.items():
            if not await session.get(Team, team_id):
                session.add(Team(team_id=team_id, display_name=display_name,
                                 synthetic_assignment=True))
        await session.flush()

    # Agents
    async with get_db_session() as session:
        for agent_id, display_name in AGENT_NAMES.items():
            if not await session.get(Agent, agent_id):
                idx = int(agent_id.split("_")[1])
                team_idx = idx // AGENTS_PER_TEAM
                session.add(Agent(agent_id=agent_id, display_name=display_name,
                                  team_id=f"team_{team_idx:02d}",
                                  synthetic_assignment=True))
        await session.flush()

    # Users from SEED_USERS env var: "username:password:role,..."
    async with get_db_session() as session:
        for entry in s.seed_users.split(","):
            parts = entry.strip().split(":")
            if len(parts) != 3:
                continue
            username, password, role = parts
            existing = (await session.execute(
                select(User).where(User.username == username)
            )).scalar_one_or_none()
            if not existing:
                session.add(User(
                    username=username,
                    password_hash=hash_password(password),
                    role=role,
                    is_active=True,
                ))
                logger.info("Created user: %s (%s)", username, role)
        await session.flush()

    logger.info("Seed complete. Teams=%d Agents=%d", NUM_TEAMS, NUM_AGENTS)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    s = get_settings()
    init_db(s.database_url)
    asyncio.run(seed())


if __name__ == "__main__":
    main()
