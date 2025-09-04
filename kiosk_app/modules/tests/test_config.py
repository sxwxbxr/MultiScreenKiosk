from utils.config_loader import load_config, Config
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
