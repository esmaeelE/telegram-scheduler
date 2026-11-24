import os
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from unittest import mock
from zoneinfo import ZoneInfo

from telegram_scheduler.config import (
    ConfigError,
    build_settings,
    load_env_file,
    parse_contacts,
    parse_send_at,
)


def base_args(**overrides):
    data = dict(
        api_id=123456,
        api_hash="hash",
        session="test_session",
        contacts="alice,bob",
        message="hello",
        message_file=None,
        at="2099-01-01T09:00",
        now=False,
        timezone="Asia/Baku",
        dry_run=False,
        list_dialogs=False,
        retries=2,
        json=False,
    )
    data.update(overrides)
    return Namespace(**data)


class ConfigTests(unittest.TestCase):
    def test_parse_contacts_normalizes_and_dedupes(self):
        self.assertEqual(parse_contacts("@alice, bob, alice,, +123"), ["alice", "bob", "+123"])

    def test_parse_send_at_accepts_space_and_naive_timezone(self):
        tz = ZoneInfo("Asia/Baku")
        dt = parse_send_at("2099-01-01 09:00", tz)
        self.assertEqual(dt.tzinfo, tz)
        self.assertEqual(dt.hour, 9)

    def test_build_settings_requires_future_time(self):
        with self.assertRaises(ConfigError):
            build_settings(base_args(at="2000-01-01T09:00"))

    def test_build_settings_dry_run_allows_missing_api_credentials(self):
        settings = build_settings(base_args(api_id=None, api_hash=None, dry_run=True))
        self.assertTrue(settings.dry_run)
        self.assertIsNone(settings.api_id)

    def test_message_file_overrides_message(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "msg.txt"
            path.write_text("from file", encoding="utf-8")
            settings = build_settings(
                base_args(message="ignored", message_file=str(path), dry_run=True)
            )
            self.assertEqual(settings.message, "from file")

    def test_now_conflicts_with_missing_at_are_ok(self):
        settings = build_settings(base_args(at=None, now=True, dry_run=True))
        self.assertTrue(settings.send_now)
        self.assertIsNone(settings.send_at)

    def test_missing_required_fields_raises(self):
        with self.assertRaises(ConfigError):
            build_settings(base_args(contacts="", dry_run=True))

    def test_load_env_file_does_not_override_existing(self):
        with tempfile.TemporaryDirectory() as td:
            env = Path(td) / ".env"
            env.write_text("TG_MESSAGE=from_env\nTG_TIMEZONE=Asia/Baku\n", encoding="utf-8")
            with mock.patch.dict(os.environ, {"TG_MESSAGE": "existing"}, clear=False):
                os.environ.pop("TG_TIMEZONE", None)
                load_env_file(env)
                self.assertEqual(os.environ.get("TG_MESSAGE"), "existing")
                self.assertEqual(os.environ.get("TG_TIMEZONE"), "Asia/Baku")
                os.environ.pop("TG_TIMEZONE", None)


if __name__ == "__main__":
    unittest.main()
