"""
Seed the tasks table with N rows, then run EXPLAIN ANALYZE
before and after creating an index on the `done` column.

Usage:
    python scripts/seed_explain.py [--rows 10000]

Requires DATABASE_URL in .env or environment.
"""

import argparse
import asyncio
import os
import random
import string

from dotenv import load_dotenv

load_dotenv()

import asyncpg


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--rows", type=int, default=10000, help="Number of rows to seed"
    )
    args = parser.parse_args()

    url = os.getenv("DATABASE_URL")
    if not url:
        print("DATABASE_URL not set")
        return

    conn = await asyncpg.connect(url)

    titles = [
        "".join(random.choices(string.ascii_letters, k=random.randint(5, 30)))
        for _ in range(args.rows)
    ]

    print(f"Seeding {args.rows} rows...")
    await conn.executemany(
        "INSERT INTO tasks (title, done, created_at, updated_at) VALUES ($1, $2, NOW(), NOW())",
        [(t, random.choice([True, False])) for t in titles],
    )
    print("Seeding done.\n")

    query = "SELECT * FROM tasks WHERE done = TRUE ORDER BY id"

    print("=== BEFORE INDEX ===")
    before = await conn.execute(f"EXPLAIN ANALYZE {query}")
    print(before)

    print("\nCreating index idx_tasks_done on tasks(done)...")
    await conn.execute("DROP INDEX IF EXISTS idx_tasks_done")
    await conn.execute("CREATE INDEX idx_tasks_done ON tasks(done)")
    print("Index created.\n")

    print("=== AFTER INDEX ===")
    after = await conn.execute(f"EXPLAIN ANALYZE {query}")
    print(after)

    count = await conn.fetchval("SELECT COUNT(*) FROM tasks")
    print(f"\nTotal rows in tasks: {count}")

    await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
