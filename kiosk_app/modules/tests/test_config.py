from utils.config_loader import load_config, Config, DEFAULT_SHORTCUTS
from pathlib import Path
import json
import tempfile

def test_valid_config_loads(tmp_path: Path):
    cfg_data = {
        "browser_urls": ["http://127.0.0.1:8000","http://127.0.0.1:8001","http://127.0.0.1:8002"],
        "local_app": {"launch_cmd":"notepad.exe","embed_mode":"native_window","window_title_pattern":".*Notepad.*"},
        "ui": {"start_mode":"single","sidebar_width":96, "split_enabled": False},
        "kiosk": {"monitor_index":0,"disable_system_keys":True}
    }
    p = tmp_path / "config.json"
    p.write_text(json.dumps(cfg_data))
    cfg = load_config(p)
    assert isinstance(cfg, Config)
    assert cfg.ui.start_mode == "single"
    assert cfg.ui.split_enabled is False

def test_invalid_urls(tmp_path: Path):
    cfg_data = {
        "browser_urls": ["abc","def","ghi"],
        "local_app": {"launch_cmd":"notepad.exe"}
    }
    p = tmp_path / "config.json"
    p.write_text(json.dumps(cfg_data))
    try:
        load_config(p)
    except Exception as e:
        assert "http" in str(e)


def test_shortcuts_override(tmp_path: Path):
    cfg_data = {
        "sources": [{"type": "browser", "name": "A", "url": "http://example.com"}],
        "ui": {"shortcuts": {"toggle_kiosk": "Ctrl+F"}},
    }
    p = tmp_path / "config.json"
    p.write_text(json.dumps(cfg_data))
    cfg = load_config(p)
    assert cfg.ui.shortcuts["toggle_kiosk"] == "Ctrl+F"
    assert cfg.ui.shortcuts["select_1"] == DEFAULT_SHORTCUTS["select_1"]


def test_remote_logging_settings(tmp_path: Path):
    cfg_data = {
        "sources": [{"type": "browser", "name": "A", "url": "http://example.com"}],
        "logging": {
            "remote_export": {
                "enabled": True,
                "include_history": 2,
                "source_glob": "*.log",
                "schedule_minutes": 15,
                "destinations": [
                    {
                        "type": "http",
                        "name": "api",
                        "url": "https://example.com/upload",
                        "headers": {"X-Test": "1"},
                    },
                    {
                        "type": "email",
                        "smtp_host": "smtp.example.com",
                        "email_from": "kiosk@example.com",
                        "email_to": ["ops@example.com"],
                        "use_tls": True,
                    },
                ],
            }
        }
    }
    p = tmp_path / "config.json"
    p.write_text(json.dumps(cfg_data))
    cfg = load_config(p)
    remote = cfg.logging.remote_export
    assert remote.enabled is True
    assert remote.include_history == 2
    assert remote.source_glob == "*.log"
    assert remote.schedule_minutes == 15
    assert len(remote.destinations) == 2
    http_dest = remote.destinations[0]
    email_dest = remote.destinations[1]
    assert http_dest.type == "http"
    assert http_dest.url == "https://example.com/upload"
    assert email_dest.type == "email"
    assert email_dest.smtp_host == "smtp.example.com"
    assert email_dest.email_to == ["ops@example.com"]


def test_remote_logging_retention(tmp_path: Path):
    cfg_data = {
        "sources": [{"type": "browser", "name": "A", "url": "http://example.com"}],
        "logging": {
            "remote_export": {
                "enabled": True,
                "retention_count": None,
                "retention_days": -1,
                "schedule_minutes": 0,
            }
        },
    }
    path = tmp_path / "config.json"
    path.write_text(json.dumps(cfg_data))
    cfg = load_config(path)
    remote = cfg.logging.remote_export
    assert remote.retention_count is None
    assert remote.retention_days is None
    assert remote.schedule_minutes is None


def test_update_settings_parse(tmp_path: Path):
    cfg_data = {
        "sources": [{"type": "browser", "name": "A", "url": "http://example.com"}],
        "updates": {
            "enabled": True,
            "feed_url": "https://example.com/feed.json",
            "channel": "beta",
            "check_interval_hours": 12,
            "verify_tls": False,
            "download_dir": str(tmp_path / "downloads"),
            "auto_install": False,
        }
    }
    path = tmp_path / "config.json"
    path.write_text(json.dumps(cfg_data))
    cfg = load_config(path)
    updates = cfg.updates
    assert updates.enabled is True
    assert updates.feed_url == "https://example.com/feed.json"
    assert updates.channel == "beta"
    assert updates.check_interval_hours == 12
    assert updates.verify_tls is False
    assert updates.download_dir == str(tmp_path / "downloads")
    assert updates.auto_install is False


def test_schedule_parsing(tmp_path: Path):
    cfg_data = {
        "sources": [
            {"type": "browser", "name": "A", "url": "http://example.com"},
            {"type": "browser", "name": "B", "url": "http://example.org"},
            {"type": "browser", "name": "C", "url": "http://example.net"},
        ],
        "schedules": [
            {
                "pane": 0,
                "default_source": "A",
                "blocks": [
                    {"start": "08:00", "end": "10:00", "source": "B"},
                    {"start": "10:00", "end": "18:00", "source": "C"},
                ],
            },
            {
                "pane": 1,
                "blocks": [
                    {"start": "00:00", "end": "23:59", "source": "A"},
                    {"start": "bad", "end": "value", "source": "ignored"},
                ],
            },
            {"pane": -1, "blocks": [{"start": "00:00", "end": "01:00", "source": "B"}]},
        ],
    }
    path = tmp_path / "config.json"
    path.write_text(json.dumps(cfg_data))
    cfg = load_config(path)

    assert len(cfg.schedules) == 2
    first = cfg.schedules[0]
    assert first.pane == 0
    assert first.default_source == "A"
    assert [block.source for block in first.blocks] == ["B", "C"]
    assert first.blocks[0].start == "08:00"
    assert first.blocks[1].end == "18:00"

    second = cfg.schedules[1]
    assert second.pane == 1
    assert second.default_source is None
    assert len(second.blocks) == 1
    assert second.blocks[0].source == "A"
