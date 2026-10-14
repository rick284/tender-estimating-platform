from __future__ import annotations
from typing import Any

import config

_db: Any = None


def get_db() -> Any:
    global _db
    if _db is None:
        if config.USE_MOCK_DB or not config.MONGO_URL:
            if config.IS_PROD:
                raise RuntimeError("No database configured")
            from mongomock_motor import AsyncMongoMockClient
            _db = AsyncMongoMockClient()[config.DB_NAME]
        else:
            from motor.motor_asyncio import AsyncIOMotorClient
            _db = AsyncIOMotorClient(config.MONGO_URL, serverSelectionTimeoutMS=8000)[config.DB_NAME]
    return _db


def set_db(db: Any) -> None:
    """Tests inject an isolated in-memory database."""
    global _db
    _db = db


async def ensure_indexes(db: Any) -> None:
    await db.users.create_index("email", unique=True)
    await db.tenders.create_index([("org_id", 1), ("updated_at", -1)])
    await db.revisions.create_index([("tender_id", 1), ("n", 1)], unique=True)
    await db.revisions.create_index("org_id")
    await db.login_attempts.create_index("ts", expireAfterSeconds=config.LOGIN_WINDOW_MINUTES * 60)
    await db.audit.create_index([("org_id", 1), ("ts", -1)])
    await db.ai_proposals.create_index([("org_id", 1), ("tender_id", 1), ("created_at", -1)])
    await db.programme_docs.create_index([("org_id", 1), ("tender_id", 1), ("updated_at", -1)])
    await db.time_sessions.create_index([("org_id", 1), ("user_id", 1), ("started_at", -1)])
    await db.ai_runs.create_index([("org_id", 1), ("user_id", 1), ("started_at", -1)])
    await db.time_entries.create_index([("org_id", 1), ("user_id", 1), ("date", -1)])
    await db.doc_texts.create_index([("org_id", 1), ("tender_id", 1)])
