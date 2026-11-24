# Telegram Scheduler

A small, configurable Telegram CLI for sending or scheduling the same message to multiple contacts using [Telethon](https://docs.telethon.dev/).

It uses Telegram's native messaging/scheduling APIs: when you run it, the tool connects to Telegram and sends or schedules messages for the requested time. It is not a long-running local daemon.

## Features

- **Send now or schedule** - deliver immediately with `--now`, or schedule with `--at`.
- **Configurable** - CLI flags, environment variables, or a local `.env` file.
- **Timezone-aware** - naive datetimes are interpreted in an explicit timezone (`Asia/Baku` by default).
- **Dry-run mode** - validate and preview targets without contacting Telegram.
- **Dialog discovery** - `--list-dialogs` helps find usernames/chat IDs for `TG_CONTACTS`.
- **Retry handling** - retryable failures are retried with backoff.
- **JSON output** - `--json` emits machine-readable results to stdout.
- **Actionable errors** - unresolved contacts include guidance on how to fix them.

## Prerequisites

- [uv](https://docs.astral.sh/uv/)
- Python 3.10+
- Telegram API credentials from [my.telegram.org/apps](https://my.telegram.org/apps)

## Setup

1. **Install dependencies**

   ```bash
   uv sync
   ```

2. **Create local config**

   ```bash
   cp .env.example .env
   ```

3. **Add your Telegram API credentials**

   - Open [my.telegram.org/apps](https://my.telegram.org/apps)
   - Log in with your phone number and confirmation code
   - Open **API development tools** and create an app if needed
   - Copy `App api_id` and `App api_hash` into `.env`:

   ```env
   TG_API_ID=123456
   TG_API_HASH=0123456789abcdef0123456789abcdef
   ```

## Usage

### Preview (recommended)

```bash
uv run telegram-scheduler --dry-run
```

### Schedule messages

```bash
uv run telegram-scheduler
```

### Send immediately

```bash
uv run telegram-scheduler --now
```

### List dialogs to find contact identifiers

```bash
uv run telegram-scheduler --list-dialogs
```

### CLI overrides

```bash
uv run telegram-scheduler \
  --contacts alice,+1234567890 \
  --message "Hello" \
  --at "2026-11-24 09:00" \
  --timezone Asia/Baku
```

You can also run the module directly:

```bash
uv run python -m telegram_scheduler --dry-run
```

## Configuration

Configuration precedence: **CLI flags > environment variables > `.env`**. Existing process environment variables are not overridden by `.env`.

| CLI flag | Env var | Required | Description |
| --- | --- | --- | --- |
| `--api-id` | `TG_API_ID` | Yes, except `--dry-run` without `--list-dialogs` | Telegram API ID. |
| `--api-hash` | `TG_API_HASH` | Yes, except `--dry-run` without `--list-dialogs` | Telegram API hash. |
| `--session` | `TG_SESSION` | No | Telethon session name/path. Default: `telegram_scheduler`. |
| `--contacts` | `TG_CONTACTS` | Yes for send/schedule | Comma-separated usernames, phone numbers, or chat IDs. |
| `--message` | `TG_MESSAGE` | Yes for send/schedule | Message text. |
| `--message-file` | - | No | Read message from a UTF-8 text file (overrides `--message`). |
| `--at` | `TG_SEND_AT` | Yes unless `--now` | Schedule time. ISO 8601; naive values use `TG_TIMEZONE`. |
| `--now` | - | No | Send immediately instead of scheduling. |
| `--timezone` | `TG_TIMEZONE` | No | Timezone for naive `--at`. Default: `Asia/Baku`. |
| `--dry-run` | - | No | Validate/preview without sending or scheduling. |
| `--list-dialogs` | - | No | Print recent dialogs and exit. |
| `--retries` | `TG_RETRIES` | No | Retry count for retryable failures. Default: `2`. |
| `--json` | - | No | Emit machine-readable JSON to stdout. |
| `--version` | - | No | Show version and exit. |

## Date/time formats

Accepted `--at` / `TG_SEND_AT` formats include:

- `2026-11-24T09:00`
- `2026-11-24T09:00:00`
- `2026-11-24 09:00`
- `2026-11-24T09:00:00+04:00`
- `2026-11-24T05:00:00Z`

If no timezone/offset is provided, the value is interpreted in `TG_TIMEZONE` / `--timezone`.

## Exit codes

| Code | Meaning |
| --- | --- |
| `0` | Success (all messages processed, dialogs listed, or dry-run completed). |
| `1` | One or more messages failed, or an unexpected runtime error occurred. |
| `2` | Invalid/missing configuration. |
| `130` | Interrupted by user. |

## Security notes

- **Do not commit secrets.** `.env` and Telethon session files (`*.session*`) are ignored by git.
- **Protect session files.** A Telethon session can authorize Telegram account access.
- **Prefer environment/secret managers** in shared or automated environments.

## Project structure

```text
.
├── src/
│   └── telegram_scheduler/   # Package: CLI, config, models, Telegram service
├── tests/                    # Unit tests
├── .env.example              # Sample configuration
├── pyproject.toml            # Project metadata and dependencies
└── uv.lock                   # Locked dependency versions
```

## Development

Run tests:

```bash
uv run python -m unittest discover -s tests -v
```

Lint and format:

```bash
uvx ruff check .
uvx ruff format .
```

## Troubleshooting

- **`Cannot find any entity corresponding to ...`** - the contact is not a resolvable username/phone/ID. Use `--list-dialogs` to find the correct `username` or `id`.
- **First real run asks for login** - normal Telethon behavior; complete phone/code/2FA prompts. Session is stored in the configured session file.
- **Scheduled time in the past** - set `TG_SEND_AT`/`--at` to a future time in the configured timezone.
