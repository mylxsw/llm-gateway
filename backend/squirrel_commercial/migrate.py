"""Explicit schema initialization or maintenance-mode v1 upgrade."""
import argparse
import asyncio
import json
import os
from sqlalchemy.ext.asyncio import create_async_engine
from .migration import initialize, upgrade


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--from-version', type=int, choices=[1])
    parser.add_argument('--to-version', type=int, choices=[2])
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--dry-run', action='store_true')
    mode.add_argument('--apply', action='store_true')
    parser.add_argument('--backup-ref')
    args = parser.parse_args()
    engine = create_async_engine(os.environ['DATABASE_URL'])
    try:
        if args.from_version == 1 and args.to_version == 2:
            print(json.dumps(await upgrade(engine, apply=args.apply, backup_ref=args.backup_ref)))
        elif args.from_version or args.to_version or args.dry_run or args.apply:
            parser.error('upgrade requires --from-version 1 --to-version 2')
        else:
            await initialize(engine)
    finally:
        await engine.dispose()


if __name__ == '__main__':
    asyncio.run(main())
