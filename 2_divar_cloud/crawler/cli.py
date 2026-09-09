import sys
import logging
import argparse
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("divar.cli")

from crawler.db import db
from crawler.engine import divar_crawler
from crawler.divar_adapter import DivarAdapter

def cmd_reset_db():
    print("⚠️ WIPING AND REBUILDING DIVAR DATABASE...")
    drop_sql = """
    DROP TABLE IF EXISTS divar_price_events CASCADE;
    DROP TABLE IF EXISTS divar_price_observations CASCADE;
    DROP TABLE IF EXISTS divar_posts CASCADE;
    DROP TABLE IF EXISTS divar_categories CASCADE;
    DROP TABLE IF EXISTS divar_crawl_logs CASCADE;
    """
    try:
        db.execute_script(drop_sql)
        print("🗑️ All Divar tables dropped.")
    except Exception as e:
        print(f"Note dropping tables: {e}")

    cmd_init_db(seed=True)
    print("✨ Divar Database reset to clean state.")

def cmd_init_db(seed: bool = True):
    schema_path = Path(__file__).resolve().parent.parent / "database" / "schema.sql"
    with open(schema_path, "r", encoding="utf-8") as f:
        sql = f.read()
    db.execute_script(sql)
    print("✅ Divar Schema created.")

    if seed:
        seed_path = Path(__file__).resolve().parent.parent / "database" / "seed_data.sql"
        if seed_path.exists():
            with open(seed_path, "r", encoding="utf-8") as f:
                seed_sql = f.read()
            db.execute_script(seed_sql)
            print("✅ Divar Categories inserted.")

def cmd_test_db():
    print("🔍 Testing connection to CockroachDB...")
    health = db.check_health()
    if health.get("connected"):
        print(f"🟢 Connected to {health.get('database_name')}")
        print(f"⚡ Latency Ping: {health.get('latency_ms')} ms")
    else:
        print(f"🔴 Connection Failed: {health.get('error')}")

def cmd_test_divar():
    print("🔍 Probing Divar API reachability...")
    adapter = DivarAdapter()
    res = adapter.probe_connection()
    if res.get("reachable"):
        print(f"🟢 Divar API is Reachable (Status: {res.get('status_code')}, Ping: {res.get('latency_ms')}ms)")
        print(f"📦 Ads received: {res.get('items_found')}")
    else:
        print(f"🔴 Divar API Unreachable (Error: {res.get('error')})")

def cmd_crawl():
    print("🚀 Starting Continuous 24/7 Divar Crawler on Render...")
    divar_crawler.run_continuous_loop()

def main():
    parser = argparse.ArgumentParser(prog="divar.cli", description="Divar Crawler CLI")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("init-db", help="Initialize schema and seed categories")
    subparsers.add_parser("reset-db", help="Reset all tables to zero")
    subparsers.add_parser("crawl", help="Start continuous Divar crawler")
    subparsers.add_parser("test-db", help="Test CockroachDB connection")
    subparsers.add_parser("test-divar", help="Test Divar API reachability")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "init-db":
        cmd_init_db(seed=True)
    elif args.command == "reset-db":
        cmd_reset_db()
    elif args.command == "crawl":
        cmd_crawl()
    elif args.command == "test-db":
        cmd_test_db()
    elif args.command == "test-divar":
        cmd_test_divar()

if __name__ == "__main__":
    main()
