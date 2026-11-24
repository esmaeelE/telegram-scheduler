from __future__ import annotations

import asyncio
import logging
from typing import Any

from .config import Settings
from .models import SendResult

logger = logging.getLogger(__name__)


def _load_telethon():
    try:
        from telethon import TelegramClient
    except ModuleNotFoundError as exc:
        raise RuntimeError("Telethon is required. Install dependencies with: uv sync") from exc
    return TelegramClient


def _entity_hint(contact: str) -> str:
    return (
        f"Could not resolve contact {contact!r}. "
        "Use a Telegram username, phone number, or chat ID. "
        "Run with --list-dialogs to discover valid identifiers."
    )


def format_send_error(exc: Exception, contact: str) -> str:
    msg = str(exc)
    if isinstance(exc, ValueError) and "Cannot find any entity corresponding to" in msg:
        return _entity_hint(contact)
    return f"{exc.__class__.__name__}: {msg}" if msg else exc.__class__.__name__


def is_retryable(exc: Exception) -> bool:
    name = exc.__class__.__name__
    if name in {
        "FloodWaitError",
        "SlowModeWaitError",
        "ServerError",
        "TimedOutError",
        "RpcCallFailError",
    }:
        return True
    msg = str(exc).lower()
    return "timeout" in msg or "temporar" in msg or "connection" in msg


async def list_dialogs(settings: Settings, limit: int = 30) -> list[dict[str, Any]]:
    TelegramClient = _load_telethon()
    dialogs: list[dict[str, Any]] = []
    async with TelegramClient(settings.session, settings.api_id, settings.api_hash) as client:
        async for dialog in client.iter_dialogs(limit=limit):
            entity = dialog.entity
            dialogs.append(
                {
                    "name": dialog.name,
                    "username": getattr(entity, "username", None),
                    "id": getattr(entity, "id", None),
                    "type": entity.__class__.__name__,
                }
            )
    return dialogs


async def _send_one(client, settings: Settings, contact: str) -> SendResult:
    last_error: str | None = None
    attempts = 0
    for attempt in range(settings.retries + 1):
        attempts = attempt + 1
        try:
            if settings.send_now:
                await client.send_message(contact, settings.message)
                return SendResult(contact=contact, ok=True, action="sent", attempts=attempts)

            await client.send_message(contact, settings.message, schedule=settings.send_at)
            return SendResult(
                contact=contact,
                ok=True,
                action="scheduled",
                scheduled_for=settings.send_at.isoformat() if settings.send_at else None,
                attempts=attempts,
            )
        except Exception as exc:  # noqa: BLE001 - actionable per-contact reporting
            last_error = format_send_error(exc, contact)
            if attempt >= settings.retries or not is_retryable(exc):
                logger.exception("Failed to process contact %s", contact)
                break
            delay = min(2**attempt, 8)
            logger.warning(
                "Retryable error for %s (attempt %d/%d): %s; retrying in %ds",
                contact,
                attempts,
                settings.retries + 1,
                last_error,
                delay,
            )
            await asyncio.sleep(delay)

    return SendResult(
        contact=contact,
        ok=False,
        action="send_now" if settings.send_now else "schedule",
        scheduled_for=settings.send_at.isoformat() if settings.send_at else None,
        error=last_error,
        attempts=attempts,
    )


async def schedule_messages(settings: Settings) -> list[SendResult]:
    TelegramClient = _load_telethon()

    if settings.send_now:
        logger.info("Sending %d message(s) now", len(settings.contacts))
    else:
        assert settings.send_at is not None
        logger.info(
            "Scheduling %d message(s) for %s",
            len(settings.contacts),
            settings.send_at.isoformat(),
        )

    for contact in settings.contacts:
        logger.info("Target: %s", contact)

    if settings.dry_run:
        logger.info("Dry run enabled; no messages were sent/scheduled.")
        return [
            SendResult(
                contact=contact,
                ok=True,
                action="dry-run",
                scheduled_for=settings.send_at.isoformat() if settings.send_at else None,
            )
            for contact in settings.contacts
        ]

    results: list[SendResult] = []
    async with TelegramClient(settings.session, settings.api_id, settings.api_hash) as client:
        for contact in settings.contacts:
            result = await _send_one(client, settings, contact)
            results.append(result)
            if result.ok:
                if result.action == "sent":
                    logger.info("Sent to %s", contact)
                else:
                    logger.info("Scheduled for %s at %s", contact, result.scheduled_for)
            else:
                logger.error("%s: %s", contact, result.error)

    failures = [result for result in results if not result.ok]
    if failures:
        logger.error("%d/%d message(s) failed.", len(failures), len(results))
    else:
        logger.info("All messages processed successfully.")
    return results
