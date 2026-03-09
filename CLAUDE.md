# Business Assistant Calendar Plugin - Development Guide

## Project Overview

Google Calendar plugin for Business Assistant v2. Source code in `src/business_assistant_calendar/`.

## Commands

- `uv sync --all-extras` — Install dependencies
- `uv run pytest tests/ -v` — Run tests
- `uv run ruff check src/ tests/` — Lint
- `uv run mypy src/` — Type check

## Architecture

- `config.py` — CalendarSettings (frozen dataclass)
- `constants.py` — Plugin-specific string constants
- `calendar_client.py` — GoogleCalendarClient (OAuth2 + Google Calendar API)
- `calendar_service.py` — High-level calendar operations (string-returning)
- `plugin.py` — Plugin registration + PydanticAI tool definitions
- `__init__.py` — Exposes `register()` as entry point

## Plugin Protocol

The plugin exposes `register(registry: PluginRegistry)` which:
1. Loads Google Calendar settings from env vars
2. Skips registration if GOOGLE_CALENDAR_CREDENTIALS_PATH not configured
3. Creates CalendarService and registers 8 PydanticAI tools

## Rules

- Use objects for related values (DTOs/Settings)
- Centralize string constants in `constants.py`
- Tests are mandatory — use pytest with mocked Google Calendar API
- Use `spec=` with MagicMock
- Type hints on all public APIs
- Frozen dataclasses for settings
