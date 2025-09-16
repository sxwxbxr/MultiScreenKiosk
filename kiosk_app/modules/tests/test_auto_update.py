from __future__ import annotations

import hashlib
import io
from pathlib import Path
from typing import Dict, Optional
from zipfile import ZipFile

from services import auto_update as auto_update_module
from services.auto_update import AutoUpdateService
from utils.config_loader import UpdateSettings


class DummyResponse:
    def __init__(self, *, json_data: Optional[Dict] = None, content: bytes = b"", status: int = 200):
        self._json = json_data
        self._content = content
        self.status_code = status

    def json(self):
        if self._json is None:
            raise ValueError("no json payload configured")
        return self._json

    def iter_content(self, chunk_size: int = 65536):
        for idx in range(0, len(self._content), chunk_size):
            yield self._content[idx : idx + chunk_size]

    def close(self):  # pragma: no cover - compatibility hook
        pass


def _create_package(**files: str) -> bytes:
    buffer = io.BytesIO()
    with ZipFile(buffer, "w") as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return buffer.getvalue()


def _auto_update_service(tmp_path: Path, feed_url: str = "https://updates.example.com/feed.json") -> AutoUpdateService:
    settings = UpdateSettings(
        enabled=True,
        feed_url=feed_url,
        verify_tls=False,
        download_dir=str(tmp_path / "downloads"),
    )
    install_dir = tmp_path / "install"
    install_dir.mkdir()
    (install_dir / "app.txt").write_text("old")
    return AutoUpdateService(settings, install_dir=install_dir, current_version="0.9.0")


def test_auto_update_installs_release(tmp_path: Path, monkeypatch):
    package_bytes = _create_package(**{"app.txt": "new", "new.txt": "fresh"})
    sha = hashlib.sha256(package_bytes).hexdigest()

    responses = {
        "https://updates.example.com/feed.json": DummyResponse(
            json_data={
                "releases": [
                    {
                        "version": "1.0.0",
                        "channel": "stable",
                        "url": "https://updates.example.com/pkg.zip",
                        "sha256": sha,
                    }
                ]
            }
        ),
        "https://updates.example.com/pkg.zip": DummyResponse(content=package_bytes),
    }

    def fake_get(url, *args, **kwargs):
        resp = responses.get(url)
        if resp is None:
            raise AssertionError(f"unexpected url {url}")
        return resp

    monkeypatch.setattr(auto_update_module.requests, "get", fake_get)

    service = _auto_update_service(tmp_path)
    result = service.run_once()

    assert result is not None
    assert result.installed is True
    assert result.release is not None and result.release.version == "1.0.0"

    install_dir = Path(service.install_dir)
    assert (install_dir / "app.txt").read_text() == "new"
    assert (install_dir / "new.txt").exists()


def test_auto_update_rollback_on_failure(tmp_path: Path, monkeypatch):
    package_bytes = _create_package(**{"app.txt": "new", "new.txt": "fresh"})
    sha = hashlib.sha256(package_bytes).hexdigest()

    responses = {
        "https://updates.example.com/feed.json": DummyResponse(
            json_data={
                "releases": [
                    {
                        "version": "1.0.0",
                        "channel": "stable",
                        "url": "https://updates.example.com/pkg.zip",
                        "sha256": sha,
                    }
                ]
            }
        ),
        "https://updates.example.com/pkg.zip": DummyResponse(content=package_bytes),
    }

    def fake_get(url, *args, **kwargs):
        resp = responses.get(url)
        if resp is None:
            raise AssertionError(f"unexpected url {url}")
        return resp

    monkeypatch.setattr(auto_update_module.requests, "get", fake_get)

    original_copy2 = auto_update_module.shutil.copy2

    def failing_copy2(src, dst, *args, **kwargs):
        if Path(dst).name == "new.txt":
            raise OSError("simulated failure")
        return original_copy2(src, dst, *args, **kwargs)

    monkeypatch.setattr(auto_update_module.shutil, "copy2", failing_copy2)

    service = _auto_update_service(tmp_path)
    result = service.run_once()

    assert result is not None
    assert result.installed is False
    assert result.error is not None
    assert result.rolled_back is True

    install_dir = Path(service.install_dir)
    assert (install_dir / "app.txt").read_text() == "old"
    assert not (install_dir / "new.txt").exists()


def test_auto_update_no_new_version(tmp_path: Path, monkeypatch):
    responses = {}

    def fake_get(url, *args, **kwargs):
        responses[url] = responses.get(url, 0) + 1
        return DummyResponse(
            json_data={
                "releases": [
                    {
                        "version": "0.9.0",
                        "channel": "stable",
                        "url": "https://updates.example.com/pkg.zip",
                        "sha256": "deadbeef",
                    }
                ]
            }
        )

    monkeypatch.setattr(auto_update_module.requests, "get", fake_get)

    service = _auto_update_service(tmp_path)
    result = service.run_once()

    assert result is None
    assert responses["https://updates.example.com/feed.json"] == 1
