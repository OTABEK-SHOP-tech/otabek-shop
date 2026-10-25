import os
import sys
import tempfile
from collections.abc import AsyncIterator
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Must be set before bekstyle is imported: the engine is created at import time.
_TMP = Path(tempfile.mkdtemp(prefix="bekstyle-test-"))
os.environ.update(
    {
        "BOT_TOKEN": "42:TEST-TOKEN",
        "OWNER_SETUP_CODE": "test-owner-code-1234567890",
        "DATA_DIR": str(_TMP),
        "DATABASE_URL": f"sqlite+aiosqlite:///{(_TMP / 'test.db').as_posix()}",
    }
)

import pytest

from bekstyle.db import Base, async_session, engine, seed_categories


@pytest.fixture
async def db() -> AsyncIterator[None]:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    async with async_session() as session:
        await seed_categories(session)
    yield
    await engine.dispose()  # pooled aiosqlite connections must not outlive this test's event loop
