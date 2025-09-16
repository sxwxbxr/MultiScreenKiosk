import time
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from utils import remote_export as remote_export_module
from utils.config_loader import RemoteLogDestination, RemoteLogExportSettings
from utils.remote_export import RemoteLogExporter, RemoteExportResult


def _create_log(tmp_path: Path) -> Path:
    log_file = tmp_path / "20240101_1_kiosk.log"
    log_file.write_text("2024-01-01 00:00:00 INFO bootstrap\n")
    return log_file


def test_remote_export_http_success(tmp_path, monkeypatch):
    log_file = _create_log(tmp_path)
    settings = RemoteLogExportSettings(
        enabled=True,
        include_history=1,
        retention_count=3,
        staging_dir=str(tmp_path / "exports"),
        destinations=[
            RemoteLogDestination(
                type="http",
                name="api",
                url="https://example.com/upload",
                method="POST",
                headers={"X-Test": "1"},
                verify_tls=False,
            )
        ],
    )
    exporter = RemoteLogExporter(settings, log_path=log_file)

    called = {}

    def fake_request(method, url, **kwargs):
        called["method"] = method
        called["url"] = url
        called["files"] = kwargs.get("files")

        class Response:
            status_code = 200
            text = "ok"

        return Response()

    monkeypatch.setattr(remote_export_module.requests, "request", fake_request)

    result = exporter.export_now(reason="manual")

    assert result.ok
    assert called["url"] == "https://example.com/upload"
    assert "file" in called["files"]
    archives = list((tmp_path / "exports").glob("*.zip"))
    assert len(archives) == 1


def test_remote_export_sftp(monkeypatch, tmp_path):
    log_file = _create_log(tmp_path)
    uploads = {}

    class DummyTransport:
        def __init__(self, host_port):
            uploads["host_port"] = host_port

        def connect(self, username=None, password=None, pkey=None):
            uploads["auth"] = {"username": username, "password": password, "pkey": pkey}

        def close(self):
            uploads["closed"] = True

    class DummySFTP:
        def put(self, local, remote):
            uploads["put"] = (local, remote)

        def close(self):
            uploads["sftp_closed"] = True

    dummy_sftp = DummySFTP()

    class DummySFTPClient:
        @staticmethod
        def from_transport(transport):
            uploads["transport"] = transport
            return dummy_sftp

    monkeypatch.setattr(
        remote_export_module,
        "paramiko",
        SimpleNamespace(
            Transport=lambda host_port: DummyTransport(host_port),
            SFTPClient=DummySFTPClient,
            RSAKey=None,
            Ed25519Key=None,
            ECDSAKey=None,
        ),
    )

    settings = RemoteLogExportSettings(
        enabled=True,
        include_history=1,
        retention_count=2,
        destinations=[
            RemoteLogDestination(
                type="sftp",
                name="sftp",
                host="sftp.example.com",
                username="user",
                password="secret",
                remote_path="/tmp/export.zip",
            )
        ],
    )
    exporter = RemoteLogExporter(settings, log_path=log_file)

    result = exporter.export_now(reason="manual")

    assert result.ok
    assert uploads["host_port"] == ("sftp.example.com", 22)
    assert uploads["auth"]["username"] == "user"
    assert uploads["auth"]["password"] == "secret"
    assert uploads["put"][1] == "/tmp/export.zip"


def test_remote_export_email(monkeypatch, tmp_path):
    log_file = _create_log(tmp_path)
    sent = {}

    class DummySMTP:
        def __init__(self, host, port, timeout=None):
            sent["init"] = {"host": host, "port": port, "timeout": timeout}

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            sent["closed"] = True

        def starttls(self):
            sent["starttls"] = True

        def login(self, username, password):
            sent["login"] = (username, password)

        def send_message(self, msg, from_addr, to_addrs):
            sent["from"] = from_addr
            sent["to"] = to_addrs
            sent["message"] = msg

    monkeypatch.setattr(remote_export_module.smtplib, "SMTP", DummySMTP)

    settings = RemoteLogExportSettings(
        enabled=True,
        include_history=1,
        destinations=[
            RemoteLogDestination(
                type="email",
                name="mail",
                email_from="kiosk@example.com",
                email_to=["ops@example.com"],
                smtp_host="smtp.example.com",
                smtp_port=2525,
                username="user",
                password="secret",
                use_tls=True,
            )
        ],
    )
    exporter = RemoteLogExporter(settings, log_path=log_file)

    result = exporter.export_now(reason="manual")

    assert result.ok
    assert sent["init"]["host"] == "smtp.example.com"
    assert sent["starttls"] is True
    assert sent["login"] == ("user", "secret")
    assert sent["to"] == ["ops@example.com"]
    attachments = list(sent["message"].iter_attachments())
    assert attachments
    assert attachments[0].get_filename().endswith(".zip")


def test_remote_export_schedule(monkeypatch, tmp_path):
    log_file = _create_log(tmp_path)
    settings = RemoteLogExportSettings(enabled=True, include_history=1, retention_count=1)
    exporter = RemoteLogExporter(settings, log_path=log_file)

    calls = []

    def fake_export(reason="manual"):
        calls.append(reason)
        return RemoteExportResult(
            archive=log_file,
            files=[log_file],
            successes=[],
            failures={},
            timestamp=datetime.now(timezone.utc),
            reason=reason,
            duration=0.0,
        )

    monkeypatch.setattr(exporter, "export_now", fake_export)

    try:
        exporter.start_periodic_export(interval_seconds=0.05)
        time.sleep(0.12)
    finally:
        exporter.stop_periodic_export()

    assert any(reason == "scheduled" for reason in calls)
