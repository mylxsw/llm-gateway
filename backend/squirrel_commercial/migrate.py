"""Run explicitly AFTER the gateway's normal schema initialization."""
import asyncio
import os
from sqlalchemy.ext.asyncio import create_async_engine
from .core import migrate
async def main():
    engine = create_async_engine(os.environ['DATABASE_URL'])
    try:
        await migrate(engine)
    finally:
        await engine.dispose()
if __name__ == '__main__':
    asyncio.run(main())
