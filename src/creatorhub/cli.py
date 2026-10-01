from __future__ import annotations

import argparse
import logging
import sys

from .config import Settings, init_home


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="creatorhub", description="CreatorHub AI: your always-on content partner")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init", help="create ~/.creatorhub with a starter profile")
    serve = sub.add_parser("serve", help="run the MCP server (stdio by default)")
    serve.add_argument("--http", action="store_true", help="serve over streamable HTTP instead of stdio")
    sub.add_parser("watch", help="run the background trend watcher forever")
    scan = sub.add_parser("scan", help="run one scan and print what it found")
    scan.add_argument("--no-notify", action="store_true")
    args = parser.parse_args(argv)

    # stdout belongs to the MCP protocol in stdio mode, so logs always go to stderr.
    logging.basicConfig(level=logging.INFO, stream=sys.stderr, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    settings = Settings.load()

    if args.cmd == "init":
        print(f"Profile: {init_home(settings)}\nEdit it, then add API keys to {settings.home / '.env'}")
    elif args.cmd == "serve":
        from .server import run
        run("streamable-http" if args.http else "stdio")
    elif args.cmd == "watch":
        from .watcher import run_forever
        init_home(settings)
        run_forever(settings)
    elif args.cmd == "scan":
        from .store import Store
        from .watcher import scan as do_scan
        init_home(settings)
        store = Store(settings.db_path)
        r = do_scan(settings, store, send_notifications=not args.no_notify)
        print(f"fetched {r.fetched} items ({r.new} new), Claude judged {r.judged}, {len(r.alerts)} alerts\n")
        for a in r.alerts:
            print(f"- {a.title}\n  {a.body}\n  {a.url or ''}")
        print("\nTop trends:")
        for t in store.top_trends(limit=10):
            print(f"  {t['score']:5.1f}  [{t['matched_niche'] or '-'}] {t['title'][:90]}")


if __name__ == "__main__":
    main()
