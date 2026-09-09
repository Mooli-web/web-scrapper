import sys
import logging
import argparse
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("crawler.cli")

from crawler.db import db
from crawler.engine import crawler_engine
from crawler.divar_engine import divar_crawler_engine
from crawler.adapters.digikala import DigikalaAdapter
from crawler.adapters.divar import DivarAdapter
from crawler.storage_guard import StorageGuard

def cmd_reset_db():
    """Completely wipes and rebuilds schema from zero."""
    print("=" * 60)
    print("⚠️ WIPING AND REBUILDING DATABASE...")
    print("=" * 60)
    
    drop_sql = """
    DROP TABLE IF EXISTS price_events CASCADE;
    DROP TABLE IF EXISTS price_observations CASCADE;
    DROP TABLE IF EXISTS store_listings CASCADE;
    DROP TABLE IF EXISTS master_products CASCADE;
    DROP TABLE IF EXISTS categories CASCADE;
    DROP TABLE IF EXISTS stores CASCADE;
    DROP TABLE IF EXISTS crawl_logs CASCADE;
    """
    try:
        db.execute_script(drop_sql)
        print("🗑️ All tables dropped.")
    except Exception as e:
        print(f"Note dropping tables: {e}")

    cmd_init_db(seed=True)
    print("✨ Database reset to 100% clean state.")

def cmd_init_db(seed: bool = True):
    """Initializes tables from schema.sql."""
    schema_path = Path(__file__).resolve().parent.parent / "database" / "schema.sql"
    with open(schema_path, "r", encoding="utf-8") as f:
        sql = f.read()
    db.execute_script(sql)
    print("✅ Schema created.")

    if seed:
        seed_path = Path(__file__).resolve().parent.parent / "database" / "seed_data.sql"
        if seed_path.exists():
            with open(seed_path, "r", encoding="utf-8") as f:
                seed_sql = f.read()
            db.execute_script(seed_sql)
            print("✅ Seed categories and stores inserted.")

def cmd_test_db():
    """Tests CockroachDB live connection."""
    print("🔍 Testing connection to CockroachDB...")
    health = db.check_health()
    if health.get("connected"):
        print(f"🟢 Connected to {health.get('host')} ({health.get('database_name')})")
        print(f"⚡ Latency Ping: {health.get('latency_ms')} ms")
    else:
        print(f"🔴 Connection Failed: {health.get('error')}")
        print(f"💡 Hint: {health.get('hint')}")

def cmd_test_digikala():
    """Tests Digikala API reachability."""
    print("🔍 Probing Digikala API reachability...")
    adapter = DigikalaAdapter()
    res = adapter.probe_connection()
    if res.get("reachable"):
        print(f"🟢 Digikala API is Reachable (Status: {res.get('status_code')}, Ping: {res.get('latency_ms')}ms)")
        print(f"📦 Items received in probe: {res.get('items_found')}")
    else:
        print(f"🔴 Digikala API Unreachable (Status: {res.get('status')}, Error: {res.get('error')})")
        print(f"💡 {res.get('hint')}")

def cmd_test_divar():
    """Tests Divar API reachability."""
    print("🔍 Probing Divar API reachability...")
    adapter = DivarAdapter()
    res = adapter.probe_connection()
    if res.get("reachable"):
        print(f"🟢 Divar API is Reachable (Status: {res.get('status_code')}, Ping: {res.get('latency_ms')}ms)")
        print(f"📦 Ads received in probe: {res.get('items_found')}")
    else:
        print(f"🔴 Divar API Unreachable (Status: {res.get('status')}, Error: {res.get('error')})")
        print(f"💡 {res.get('hint')}")

def cmd_crawl_digikala():
    """Runs continuous polite crawler for Digikala."""
    print("🚀 Starting Continuous Digikala Market Crawler (24/7)...")
    crawler_engine.run_continuous_loop()

def cmd_crawl_divar():
    """Runs continuous polite crawler for Divar."""
    print("🚀 Starting Continuous Divar Market Crawler (24/7)...")
    divar_crawler_engine.run_continuous_loop()

def cmd_db_size():
    """Prints storage usage."""
    stats = StorageGuard.get_database_stats()
    print("=" * 60)
    print(f"📊 Storage Usage: {stats['estimated_storage_mb']} MB / {stats['quota_max_gb']} GB ({stats['usage_percent']}%)")
    print(f"Total Database Rows: {stats['total_rows']:,}")
    print("=" * 60)

def main():
    parser = argparse.ArgumentParser(prog="crawler.cli", description="Market Intelligence Crawler CLI")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("init-db", help="Initialize schema and seed categories")
    subparsers.add_parser("reset-db", help="Reset all tables to zero")
    subparsers.add_parser("crawl", help="Start continuous Digikala crawler")
    subparsers.add_parser("crawl-divar", help="Start continuous Divar crawler")
    subparsers.add_parser("test-db", help="Test CockroachDB connection & ping")
    subparsers.add_parser("test-digikala", help="Test Digikala API reachability")
    subparsers.add_parser("test-divar", help="Test Divar API reachability")
    subparsers.add_parser("db-size", help="View database storage footprint")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "init-db":
        cmd_init_db(seed=True)
    elif args.command == "reset-db":
        cmd_reset_db()
    elif args.command in ("crawl", "crawl-digikala"):
        cmd_crawl_digikala()
    elif args.command == "crawl-divar":
        cmd_crawl_divar()
    elif args.command == "test-db":
        cmd_test_db()
    elif args.command == "test-digikala":
        cmd_test_digikala()
    elif args.command == "test-divar":
        cmd_test_divar()
    elif args.command == "db-size":
        cmd_db_size()

if __name__ == "__main__":
    main()
