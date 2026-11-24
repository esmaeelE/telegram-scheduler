from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

DEFAULT_TIMEZONE = "Asia/Baku"
DEFAULT_SESSION = "telegram_scheduler"


@dataclass(slots=True)
class Settings:
    api_id: int | None
    api_hash: str | None
    session: str
    contacts: list[str]
    message: str | None
    send_at: datetime | None
    send_now: bool
    timezone: str
    dry_run: bool
    list_dialogs: bool
    json_output: bool
    retries: int


class ConfigError(ValueError):
    pass


def load_env_file(path: str | Path = ".env") -> None:
    """Load KEY=VALUE pairs from a local .env file without overriding existing env."""
    candidates = [Path(path)]
    script_env = Path(__file__).resolve().parent.parent / ".env"
    if script_env not in candidates:
        candidates.append(script_env)

    env_path = next((candidate for candidate in candidates if candidate.exists()), None)
    if env_path is None:
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'").replace("\\n", "\n")
        if key and key not in os.environ:
            os.environ[key] = value


def get_env(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name)
    if value is None:
        return default
    value = value.strip()
    return value if value else default


def parse_contacts(raw: str | None) -> list[str]:
    if not raw:
        return []
    contacts: list[str] = []
    for item in raw.split(","):
        contact = item.strip()
        if contact.startswith("@"):
            contact = contact[1:]
        if contact:
            contacts.append(contact)
    return list(dict.fromkeys(contacts))


def resolve_timezone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError as exc:
        raise ConfigError(f"Unknown timezone: {name}") from exc


def parse_send_at(raw: str, tz: ZoneInfo) -> datetime:
    normalized = raw.strip()
    if " " in normalized and "T" not in normalized:
        normalized = normalized.replace(" ", "T", 1)
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ConfigError(
            "Invalid --at value. Use ISO 8601, e.g. 2026-11-24T09:00 or 2026-11-24T09:00+04:00."
        ) from exc

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=tz)
    return parsed


def read_message(message: str | None, message_file: str | None) -> str | None:
    if message_file:
        path = Path(message_file)
        if not path.exists():
            raise ConfigError(f"Message file not found: {message_file}")
        content = path.read_text(encoding="utf-8")
        if not content.strip():
            raise ConfigError(f"Message file is empty: {message_file}")
        return content
    return message


def build_settings(args) -> Settings:
    timezone_name = args.timezone or get_env("TG_TIMEZONE", DEFAULT_TIMEZONE)
    tz = resolve_timezone(timezone_name)

    api_id = args.api_id
    if api_id is None:
        raw_api_id = get_env("TG_API_ID")
        if raw_api_id is not None:
            try:
                api_id = int(raw_api_id)
            except ValueError as exc:
                raise ConfigError("TG_API_ID must be an integer.") from exc

    api_hash = args.api_hash or get_env("TG_API_HASH")
    session = args.session or get_env("TG_SESSION", DEFAULT_SESSION) or DEFAULT_SESSION
    contacts = parse_contacts(args.contacts or get_env("TG_CONTACTS"))
    message = read_message(
        args.message if args.message is not None else get_env("TG_MESSAGE"),
        args.message_file,
    )
    send_now = bool(args.now)
    send_at_raw = None if send_now else (args.at or get_env("TG_SEND_AT"))
    send_at = parse_send_at(send_at_raw, tz) if send_at_raw else None

    if send_at is not None and send_at <= datetime.now(tz):
        raise ConfigError(
            f"Scheduled time {send_at.isoformat()} is not in the future "
            f"for timezone {timezone_name}."
        )

    retries = args.retries
    if retries is None:
        raw_retries = get_env("TG_RETRIES")
        if raw_retries is not None:
            try:
                retries = int(raw_retries)
            except ValueError as exc:
                raise ConfigError("TG_RETRIES must be an integer.") from exc
    if retries is None:
        retries = 2
    if retries < 0:
        raise ConfigError("--retries must be >= 0.")

    settings = Settings(
        api_id=api_id,
        api_hash=api_hash,
        session=session,
        contacts=contacts,
        message=message,
        send_at=send_at,
        send_now=send_now,
        timezone=timezone_name,
        dry_run=bool(args.dry_run),
        list_dialogs=bool(args.list_dialogs),
        json_output=bool(args.json),
        retries=retries,
    )
    validate_settings(settings)
    return settings


def validate_settings(settings: Settings) -> None:
    missing: list[str] = []
    needs_api = not settings.dry_run or settings.list_dialogs

    if settings.api_id is None and needs_api:
        missing.append("TG_API_ID/--api-id")
    if not settings.api_hash and needs_api:
        missing.append("TG_API_HASH/--api-hash")

    if settings.list_dialogs:
        if missing:
            raise ConfigError(f"Missing required configuration: {', '.join(missing)}")
        return

    if not settings.contacts:
        missing.append("TG_CONTACTS/--contacts")
    if not settings.message:
        missing.append("TG_MESSAGE/--message/--message-file")
    if not settings.send_now and settings.send_at is None:
        missing.append("TG_SEND_AT/--at/--now")

    if missing:
        raise ConfigError(f"Missing required configuration: {', '.join(missing)}")
