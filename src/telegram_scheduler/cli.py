from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys

from . import __version__
from .config import DEFAULT_TIMEZONE, ConfigError, build_settings, load_env_file
from .models import results_to_json
from .service import list_dialogs, schedule_messages


def configure_logging(json_output: bool) -> None:
    level = logging.WARNING if json_output else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stderr,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="telegram-scheduler",
        description="Schedule or send Telegram messages to multiple contacts using Telethon.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  telegram-scheduler --dry-run\n"
            "  telegram-scheduler --at 2026-11-24T09:00 --contacts alice --message 'Hi'\n"
            "  telegram-scheduler --now --contacts alice --message-file msg.txt\n"
            "  telegram-scheduler --list-dialogs\n"
        ),
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--api-id", type=int, help="Telegram API ID. Defaults to TG_API_ID.")
    parser.add_argument("--api-hash", help="Telegram API hash. Defaults to TG_API_HASH.")
    parser.add_argument("--session", help="Telethon session name/path. Defaults to TG_SESSION.")
    parser.add_argument(
        "--contacts",
        help="Comma-separated usernames, phone numbers, or chat IDs. Defaults to TG_CONTACTS.",
    )
    parser.add_argument("--message", help="Message text. Defaults to TG_MESSAGE.")
    parser.add_argument("--message-file", help="Path to a UTF-8 text file containing the message.")
    parser.add_argument("--at", help="When to send, in ISO 8601 format. Defaults to TG_SEND_AT.")
    parser.add_argument(
        "--now",
        action="store_true",
        help="Send immediately instead of scheduling.",
    )
    parser.add_argument(
        "--timezone",
        help=f"Timezone for naive --at values. Defaults to TG_TIMEZONE or {DEFAULT_TIMEZONE}.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and preview without sending/scheduling.",
    )
    parser.add_argument(
        "--list-dialogs",
        action="store_true",
        help="List recent dialogs (name, username, id) and exit.",
    )
    parser.add_argument(
        "--retries",
        type=int,
        help="Retry count for retryable send failures. Default: 2.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON to stdout.",
    )
    return parser


def _emit(payload) -> None:
    json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


async def _run(args) -> int:
    settings = build_settings(args)

    if settings.list_dialogs:
        dialogs = await list_dialogs(settings)
        if args.json:
            _emit({"ok": True, "dialogs": dialogs})
        else:
            if not dialogs:
                print("No dialogs found.")
            else:
                rows = []
                for dialog in dialogs:
                    username = f"@{dialog['username']}" if dialog["username"] else "-"
                    rows.append([dialog["name"], username, str(dialog["id"]), dialog["type"]])
                headers = ["Name", "Username", "ID", "Type"]
                widths = [len(h) for h in headers]
                for row in rows:
                    for i, cell in enumerate(row):
                        widths[i] = max(widths[i], len(cell))
                fmt = "  ".join(f"{{:<{w}}}" for w in widths)
                print(fmt.format(*headers))
                print(fmt.format(*["-" * w for w in widths]))
                for row in rows:
                    print(fmt.format(*row))
        return 0

    results = await schedule_messages(settings)
    payload = {
        "ok": all(r.ok for r in results),
        "action": "send_now" if settings.send_now else "schedule",
        "scheduled_for": settings.send_at.isoformat() if settings.send_at else None,
        "results": results_to_json(results),
    }
    if args.json:
        _emit(payload)
    return 0 if payload["ok"] else 1


def main(argv: list[str] | None = None) -> int:
    load_env_file()
    parser = build_parser()
    args = parser.parse_args(argv)
    configure_logging(args.json)

    try:
        return asyncio.run(_run(args))
    except ConfigError as exc:
        if args.json:
            _emit({"ok": False, "error": str(exc)})
        else:
            logging.error("%s", exc)
        return 2
    except KeyboardInterrupt:
        if args.json:
            _emit({"ok": False, "error": "Interrupted"})
        else:
            logging.warning("Interrupted.")
        return 130
    except Exception as exc:  # noqa: BLE001
        if args.json:
            _emit({"ok": False, "error": f"{exc.__class__.__name__}: {exc}"})
        else:
            logging.exception("Unexpected error.")
        return 1
