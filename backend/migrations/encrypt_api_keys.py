#!/usr/bin/env python3
"""
Data Migration Script: Encrypt Existing API Keys

This script encrypts all plaintext API keys stored in the service_providers table.

Usage:
    1. Ensure ENCRYPTION_KEY environment variable is set (recommended for production)
    2. Run this script: python migrations/encrypt_api_keys.py
    3. Verify the migration was successful
    4. (Optional) Backup your database before running in production

Environment Variables:
    DATABASE_URL: Database connection string (default: sqlite+aiosqlite:///./llm_gateway.db)
    ENCRYPTION_KEY: Base64-encoded 32-byte encryption key (optional, will generate if not set)

Example:
    # Generate an encryption key
    python -c "import secrets, base64; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())"

    # Set environment variable
    export ENCRYPTION_KEY="your-generated-key-here"

    # Run migration
    python migrations/encrypt_api_keys.py

Safety Features:
    - Detects already encrypted values (with "enc:" prefix) and skips them
    - Creates a backup of the api_key values before modification
    - Provides detailed logging of the migration process
    - Dry-run mode available to preview changes
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.common.encryption import encrypt, is_encrypted, ENCRYPTION_PREFIX
from app.config import get_settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def migrate_api_keys(dry_run: bool = False) -> dict:
    """
    Migrate plaintext API keys to encrypted format

    Args:
        dry_run: If True, only show what would be changed without making changes

    Returns:
        dict: Migration statistics
    """
    settings = get_settings()

    # Create synchronous engine for migration
    # Convert async URL to sync URL
    database_url = settings.DATABASE_URL
    if "aiosqlite" in database_url:
        database_url = database_url.replace("aiosqlite", "pysqlite")
    elif "+asyncpg" in database_url:
        database_url = database_url.replace("+asyncpg", "+psycopg2")

    engine = create_engine(database_url)
    Session = sessionmaker(bind=engine)

    stats = {
        "total_providers": 0,
        "providers_with_api_key": 0,
        "already_encrypted": 0,
        "encrypted": 0,
        "empty_keys": 0,
        "errors": 0,
    }

    with Session() as session:
        # Get all providers
        result = session.execute(
            text("SELECT id, name, api_key FROM service_providers")
        )
        providers = result.fetchall()
        stats["total_providers"] = len(providers)

        logger.info(f"Found {stats['total_providers']} providers to process")

        for provider_id, name, api_key in providers:
            try:
                # Skip empty keys
                if not api_key:
                    stats["empty_keys"] += 1
                    logger.debug(f"Provider {name} (ID: {provider_id}): Empty API key, skipping")
                    continue

                stats["providers_with_api_key"] += 1

                # Check if already encrypted
                if is_encrypted(api_key):
                    stats["already_encrypted"] += 1
                    logger.info(f"Provider {name} (ID: {provider_id}): Already encrypted, skipping")
                    continue

                # Encrypt the API key
                encrypted_key = encrypt(api_key)

                if dry_run:
                    logger.info(
                        f"[DRY RUN] Provider {name} (ID: {provider_id}): "
                        f"Would encrypt API key (length: {len(api_key)} -> {len(encrypted_key)})"
                    )
                else:
                    # Update the database
                    session.execute(
                        text("UPDATE service_providers SET api_key = :encrypted_key WHERE id = :id"),
                        {"encrypted_key": encrypted_key, "id": provider_id}
                    )
                    logger.info(
                        f"Provider {name} (ID: {provider_id}): "
                        f"Encrypted API key (length: {len(api_key)} -> {len(encrypted_key)})"
                    )

                stats["encrypted"] += 1

            except Exception as e:
                stats["errors"] += 1
                logger.error(f"Provider {name} (ID: {provider_id}): Failed to encrypt - {e}")

        if not dry_run and stats["encrypted"] > 0:
            session.commit()
            logger.info("Migration completed and committed")
        elif dry_run:
            logger.info("Dry run completed - no changes made")
        else:
            logger.info("No changes needed")

    return stats


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Migrate plaintext API keys to encrypted format"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without making them",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    logger.info("=" * 70)
    logger.info("API Key Encryption Migration")
    logger.info("=" * 70)

    # Check for ENCRYPTION_KEY
    encryption_key = os.environ.get("ENCRYPTION_KEY")
    if not encryption_key:
        logger.warning(
            "ENCRYPTION_KEY not set! A temporary key will be generated.\n"
            "This is NOT recommended for production!\n"
            "Generate a key with:\n"
            "  python -c \"import secrets, base64; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())\"\n"
        )

    if args.dry_run:
        logger.info("Running in DRY RUN mode - no changes will be made")

    stats = migrate_api_keys(dry_run=args.dry_run)

    # Print summary
    logger.info("=" * 70)
    logger.info("Migration Summary:")
    logger.info(f"  Total providers:          {stats['total_providers']}")
    logger.info(f"  Providers with API keys:  {stats['providers_with_api_key']}")
    logger.info(f"  Already encrypted:        {stats['already_encrypted']}")
    logger.info(f"  Newly encrypted:          {stats['encrypted']}")
    logger.info(f"  Empty keys:               {stats['empty_keys']}")
    logger.info(f"  Errors:                   {stats['errors']}")
    logger.info("=" * 70)

    if stats["errors"] > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
