"""Tests for scheduler worker request-queue helpers."""

from __future__ import annotations

import sys
import types
from unittest.mock import MagicMock

import tasks.runner as runner


def test_request_immediate_run_upserts_system_status(monkeypatch, mock_supabase_client):
    mock_table = mock_supabase_client.table.return_value
    mock_table.upsert.return_value = mock_table
    monkeypatch.setattr(runner, "_get_sb", lambda: mock_supabase_client)

    runner.request_immediate_run("user-123")

    mock_supabase_client.table.assert_called_with("system_status")
    args, kwargs = mock_table.upsert.call_args
    assert args[0]["key"] == "pipeline_request:user-123"
    assert args[0]["value"] == "requested"
    assert "updated_at" in args[0]
    assert kwargs["on_conflict"] == "key"


def test_load_requested_user_ids_returns_distinct_ids(monkeypatch, mock_supabase_client):
    mock_table = mock_supabase_client.table.return_value
    mock_table.like.return_value = mock_table
    mock_table.execute.return_value = MagicMock(
        data=[
            {"key": "pipeline_request:user-1"},
            {"key": "pipeline_request:user-2"},
            {"key": "pipeline_request:user-1"},
            {"key": "not-a-request"},
            {"key": None},
        ]
    )
    monkeypatch.setattr(runner, "_get_sb", lambda: mock_supabase_client)

    assert runner._load_requested_user_ids() == ["user-1", "user-2"]


def test_run_requested_users_processes_queued_users(monkeypatch):
    fake_module = types.ModuleType("user_config")

    class FakeUserConfig:
        def __init__(self, user_id: str):
            self.user_id = user_id

    resolved = []

    def fake_get_user_config(user_id: str):
        resolved.append(user_id)
        return FakeUserConfig(user_id)

    fake_module.get_user_config = fake_get_user_config

    monkeypatch.setattr(runner, "_load_requested_user_ids", lambda: ["user-1"])
    monkeypatch.setitem(sys.modules, "user_config", fake_module)
    monkeypatch.setattr(
        runner,
        "_run_pipeline_for_user",
        lambda user_config: {"user_id": user_config.user_id, "published": 1},
    )

    summary = runner.run_requested_users(max_workers=1)

    assert summary["users"] == 1
    assert summary["published_total"] == 1
    assert summary["results"] == [{"user_id": "user-1", "published": 1}]
    assert resolved == ["user-1"]


def test_run_all_users_resolves_config_once_per_user(monkeypatch):
    fake_module = types.ModuleType("user_config")

    class FakeUserConfig:
        def __init__(self, user_id: str):
            self.user_id = user_id

    resolved = []

    def fake_get_user_config(user_id: str):
        resolved.append(user_id)
        return FakeUserConfig(user_id)

    fake_module.get_user_config = fake_get_user_config

    monkeypatch.setattr(runner, "_load_active_user_ids", lambda: ["user-1", "user-2"])
    monkeypatch.setitem(sys.modules, "user_config", fake_module)
    monkeypatch.setattr(
        runner,
        "_run_pipeline_for_user",
        lambda user_config: {"user_id": user_config.user_id, "published": 1},
    )

    summary = runner.run_all_users(max_workers=1)

    assert summary["users"] == 2
    assert summary["published_total"] == 2
    assert sorted(resolved) == ["user-1", "user-2"]
