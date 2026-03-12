"""Tests for Calendar in-chat OAuth setup tools."""

from __future__ import annotations

import threading
from unittest.mock import MagicMock, patch

from business_assistant.agent.deps import Deps
from business_assistant.plugins.registry import PluginRegistry
from pydantic_ai import RunContext

from business_assistant_calendar.config import CalendarSettings
from business_assistant_calendar.constants import (
    PLUGIN_DATA_CALENDAR_AUTH_STATE,
    PLUGIN_DATA_CALENDAR_SETTINGS,
)
from business_assistant_calendar.plugin import (
    _calendar_complete_auth,
    _calendar_start_auth,
    register,
)


def _make_ctx(plugin_data: dict) -> RunContext[Deps]:
    """Create a minimal RunContext with the given plugin_data."""
    deps = MagicMock(spec=Deps)
    deps.plugin_data = plugin_data
    ctx = MagicMock(spec=RunContext)
    ctx.deps = deps
    return ctx


class TestStartAuth:
    @patch("business_assistant_calendar.plugin.wsgiref.simple_server.make_server")
    @patch("business_assistant_calendar.plugin.threading.Thread")
    @patch("business_assistant_calendar.calendar_client.GoogleCalendarClient")
    @patch("google_auth_oauthlib.flow.InstalledAppFlow")
    def test_generates_url_and_starts_server(
        self,
        mock_flow_cls: MagicMock,
        mock_client_cls: MagicMock,
        mock_thread_cls: MagicMock,
        mock_make_server: MagicMock,
    ) -> None:
        mock_client_cls.SCOPES = ["https://www.googleapis.com/auth/calendar"]
        mock_flow = mock_flow_cls.from_client_secrets_file.return_value
        mock_flow.authorization_url.return_value = (
            "https://accounts.google.com/o/oauth2/auth?client_id=test",
            "state_value",
        )

        settings = CalendarSettings(
            credentials_path="/tmp/creds.json",
            token_path="/tmp/token.json",
            oauth_port=51032,
        )
        plugin_data: dict = {PLUGIN_DATA_CALENDAR_SETTINGS: settings}
        ctx = _make_ctx(plugin_data)

        result = _calendar_start_auth(ctx)

        assert "https://accounts.google.com/o/oauth2/auth" in result
        assert PLUGIN_DATA_CALENDAR_AUTH_STATE in plugin_data
        auth_state = plugin_data[PLUGIN_DATA_CALENDAR_AUTH_STATE]
        assert auth_state["flow"] is mock_flow
        assert isinstance(auth_state["done"], threading.Event)
        assert not auth_state["done"].is_set()
        mock_thread_cls.return_value.start.assert_called_once()


class TestCompleteAuth:
    def test_no_session_returns_error(self) -> None:
        plugin_data: dict = {}
        ctx = _make_ctx(plugin_data)

        result = _calendar_complete_auth(ctx)

        assert "No pending authorization" in result

    def test_not_yet_received(self) -> None:
        auth_state = {
            "flow": MagicMock(),
            "response_uri": None,
            "done": threading.Event(),
            "token_path": "/tmp/token.json",
        }
        plugin_data: dict = {PLUGIN_DATA_CALENDAR_AUTH_STATE: auth_state}
        ctx = _make_ctx(plugin_data)

        result = _calendar_complete_auth(ctx)

        assert "Authorization not yet received" in result

    @patch("business_assistant_calendar.plugin.Path")
    def test_saves_token(self, mock_path_cls: MagicMock) -> None:
        mock_flow = MagicMock()
        mock_creds = MagicMock()
        mock_creds.to_json.return_value = '{"token": "abc"}'
        mock_flow.credentials = mock_creds

        done_event = threading.Event()
        done_event.set()

        auth_state = {
            "flow": mock_flow,
            "response_uri": "http://localhost:51032/?code=auth_code&state=xyz",
            "done": done_event,
            "token_path": "/tmp/token.json",
        }
        plugin_data: dict = {PLUGIN_DATA_CALENDAR_AUTH_STATE: auth_state}
        ctx = _make_ctx(plugin_data)

        mock_token_path = mock_path_cls.return_value

        result = _calendar_complete_auth(ctx)

        mock_flow.fetch_token.assert_called_once_with(
            authorization_response="https://localhost:51032/?code=auth_code&state=xyz"
        )
        mock_token_path.parent.mkdir.assert_called_once_with(
            parents=True, exist_ok=True
        )
        mock_token_path.write_text.assert_called_once_with('{"token": "abc"}')
        assert PLUGIN_DATA_CALENDAR_AUTH_STATE not in plugin_data
        assert "Google Calendar authorized" in result

    def test_failure_returns_error(self) -> None:
        mock_flow = MagicMock()
        mock_flow.fetch_token.side_effect = RuntimeError("Invalid grant")

        done_event = threading.Event()
        done_event.set()

        auth_state = {
            "flow": mock_flow,
            "response_uri": "http://localhost:51032/?code=bad&state=xyz",
            "done": done_event,
            "token_path": "/tmp/token.json",
        }
        plugin_data: dict = {PLUGIN_DATA_CALENDAR_AUTH_STATE: auth_state}
        ctx = _make_ctx(plugin_data)

        result = _calendar_complete_auth(ctx)

        assert "Authorization failed" in result
        assert "Invalid grant" in result
        assert PLUGIN_DATA_CALENDAR_AUTH_STATE not in plugin_data


class TestSetupModeRegistration:
    @patch("business_assistant_calendar.plugin.Path")
    def test_registers_auth_tools_when_no_token(
        self, mock_path_cls: MagicMock, monkeypatch
    ) -> None:
        monkeypatch.setenv("GOOGLE_CALENDAR_CREDENTIALS_PATH", "/tmp/creds.json")
        mock_path_cls.return_value.exists.return_value = False

        registry = PluginRegistry()
        register(registry)

        tools = registry.all_tools()
        assert len(tools) == 2
        tool_names = {t.name for t in tools}
        assert tool_names == {"calendar_start_auth", "calendar_complete_auth"}

    @patch("business_assistant_calendar.plugin.Path")
    def test_stores_settings_in_plugin_data(
        self, mock_path_cls: MagicMock, monkeypatch
    ) -> None:
        monkeypatch.setenv("GOOGLE_CALENDAR_CREDENTIALS_PATH", "/tmp/creds.json")
        mock_path_cls.return_value.exists.return_value = False

        registry = PluginRegistry()
        register(registry)

        assert PLUGIN_DATA_CALENDAR_SETTINGS in registry.plugin_data
        settings = registry.plugin_data[PLUGIN_DATA_CALENDAR_SETTINGS]
        assert settings.credentials_path == "/tmp/creds.json"

    @patch("business_assistant_calendar.plugin.Path")
    @patch("business_assistant_calendar.plugin.CalendarService")
    def test_normal_mode_when_token_exists(
        self, mock_service_cls: MagicMock, mock_path_cls: MagicMock, monkeypatch
    ) -> None:
        monkeypatch.setenv("GOOGLE_CALENDAR_CREDENTIALS_PATH", "/tmp/creds.json")
        mock_path_cls.return_value.exists.return_value = True

        registry = PluginRegistry()
        register(registry)

        tools = registry.all_tools()
        assert len(tools) == 9
