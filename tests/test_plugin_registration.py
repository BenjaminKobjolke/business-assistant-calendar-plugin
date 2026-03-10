"""Tests for plugin registration."""

from __future__ import annotations

from unittest.mock import patch

from business_assistant.plugins.registry import PluginRegistry

from business_assistant_calendar.constants import PLUGIN_DATA_CALENDAR_SERVICE
from business_assistant_calendar.plugin import register


class TestPluginRegistration:
    def test_register_skips_without_config(self, monkeypatch) -> None:
        monkeypatch.delenv("GOOGLE_CALENDAR_CREDENTIALS_PATH", raising=False)
        registry = PluginRegistry()
        register(registry)
        assert registry.all_tools() == []

    @patch("business_assistant_calendar.plugin.Path")
    @patch("business_assistant_calendar.plugin.CalendarService")
    def test_register_with_config(
        self, mock_service_cls, mock_path_cls, monkeypatch
    ) -> None:
        monkeypatch.setenv("GOOGLE_CALENDAR_CREDENTIALS_PATH", "/tmp/creds.json")
        mock_path_cls.return_value.exists.return_value = True

        registry = PluginRegistry()
        register(registry)

        assert len(registry.all_tools()) == 8
        assert len(registry.plugins) == 1
        assert registry.plugins[0].name == "calendar"
        assert registry.system_prompt_extras() != ""

    @patch("business_assistant_calendar.plugin.Path")
    @patch("business_assistant_calendar.plugin.CalendarService")
    def test_register_stores_service_in_plugin_data(
        self, mock_service_cls, mock_path_cls, monkeypatch
    ) -> None:
        monkeypatch.setenv("GOOGLE_CALENDAR_CREDENTIALS_PATH", "/tmp/creds.json")
        mock_path_cls.return_value.exists.return_value = True

        registry = PluginRegistry()
        register(registry)

        assert PLUGIN_DATA_CALENDAR_SERVICE in registry.plugin_data
        assert (
            registry.plugin_data[PLUGIN_DATA_CALENDAR_SERVICE]
            is mock_service_cls.return_value
        )

    @patch("business_assistant_calendar.plugin.Path")
    def test_register_without_token_registers_setup_tools(
        self, mock_path_cls, monkeypatch
    ) -> None:
        monkeypatch.setenv("GOOGLE_CALENDAR_CREDENTIALS_PATH", "/tmp/creds.json")
        mock_path_cls.return_value.exists.return_value = False

        registry = PluginRegistry()
        register(registry)

        assert len(registry.all_tools()) == 2
        assert len(registry.plugins) == 1
        assert registry.plugins[0].name == "calendar"
        assert "not yet authenticated" in registry.system_prompt_extras()
