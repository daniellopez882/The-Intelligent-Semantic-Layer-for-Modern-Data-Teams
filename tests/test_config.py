"""Settings."""

from __future__ import annotations

import pytest

from config import Settings


def build(**overrides):
    base = {"_env_file": None, "LLM_API_KEY": "k"}
    base.update(overrides)
    return Settings(**base)


class TestKeys:
    def test_the_legacy_deepseek_name_is_accepted(self, monkeypatch):
        monkeypatch.delenv("LLM_API_KEY", raising=False)
        monkeypatch.setenv("DEEPSEEK_API_KEY", "legacy")
        assert Settings(_env_file=None, LLM_API_KEY="").LLM_API_KEY == "legacy"

    def test_the_new_name_wins_when_both_are_set(self, monkeypatch):
        monkeypatch.setenv("DEEPSEEK_API_KEY", "legacy")
        assert build(LLM_API_KEY="new").LLM_API_KEY == "new"

    def test_a_missing_key_is_a_named_problem(self, monkeypatch):
        monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
        problems = build(LLM_API_KEY="").problems()
        assert any("LLM_API_KEY" in p for p in problems)


class TestBounds:
    @pytest.mark.parametrize("value", [0, -5, 100_000])
    def test_max_rows_is_bounded(self, value):
        with pytest.raises(ValueError):
            build(MAX_ROWS=value)

    def test_defaults(self):
        s = build()
        assert s.MAX_ROWS == 100
        assert s.DATABASE_URL.startswith("sqlite:///")
        assert s.LLM_BASE_URL.startswith("https://")
