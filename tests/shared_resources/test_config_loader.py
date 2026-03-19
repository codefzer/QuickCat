"""Tests for shared config_loader module."""

import json
import pytest
import config_loader


def test_load_config_returns_dict():
    cfg = config_loader.load_config()
    assert isinstance(cfg, dict)
    assert len(cfg) > 0


def test_load_servers_returns_dict():
    servers = config_loader.load_servers()
    assert isinstance(servers, dict)
    assert len(servers) > 0


def test_load_validation_rules_has_required_fields():
    rules = config_loader.load_validation_rules()
    assert isinstance(rules, dict)
    assert "required_fields" in rules


def test_load_config_missing_file_raises(tmp_path, monkeypatch):
    # lru_cache must be cleared so the patched ROOT actually triggers a file read.
    config_loader.load_config.cache_clear()
    monkeypatch.setattr(config_loader, "ROOT", tmp_path / "nonexistent")
    with pytest.raises((FileNotFoundError, OSError)):
        config_loader.load_config()
