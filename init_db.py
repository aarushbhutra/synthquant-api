#!/usr/bin/env python3
"""
Database initialization script.
Creates all tables in the PostgreSQL database (Supabase).

Usage:
    python init_db.py

This script connects to the database specified in DATABASE_URL
and creates all tables defined in models_db.py if they don't exist.

For production use with Supabase:
1. Set DATABASE_URL environment variable with your Supabase connection string
2. Run: python init_db.py

Note: This is a simple migration approach without Alembic.
For complex migrations, consider using Alembic in the future.
"""

import asyncio
import sys
import os

# Add parent directory to path for imports when running as script
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import engine, init_db, close_db
from app.models_db import Base, ApiKey, Dataset, RateLimit
from app.config import DATABASE_URL


async def main():
    """Initialize the database tables."""
    print("=" * 60)
    print("SynthQuant Database Initialization")
    print("=" * 60)
    
    # Mask password in URL for display
    display_url = DATABASE_URL
    if "@" in display_url and ":" in display_url:
        # Mask password portion
        parts = display_url.split("@")
        prefix = parts[0].rsplit(":", 1)[0]
        display_url = f"{prefix}:****@{parts[1]}"
    
    print(f"\nDatabase URL: {display_url}")
    print("\nTables to create:")
    print("  - api_keys")
    print("  - datasets")
    print("  - rate_limits")
    print()
    
    try:
        print("Connecting to database...")
        await init_db()
        print("✅ Successfully created all tables!")
        
        print("\nTable details:")
        for table_name, table in Base.metadata.tables.items():
            columns = [f"{col.name} ({col.type})" for col in table.columns]
            print(f"\n  📋 {table_name}:")
            for col in columns:
                print(f"      - {col}")
        
    except Exception as e:
        print(f"\n❌ Error creating tables: {e}")
        print("\nTroubleshooting tips:")
        print("  1. Check that DATABASE_URL is set correctly")
        print("  2. Verify your Supabase project is running")
        print("  3. Ensure the database password is correct")
        print("  4. Check network connectivity to Supabase")
        raise
    
    finally:
        print("\nClosing database connection...")
        await close_db()
        print("Done.")


if __name__ == "__main__":
    print("\n🚀 Starting database initialization...\n")
    asyncio.run(main())
