# modules/utils/remote_export.py
from __future__ import annotations

import logging
import os
import smtplib
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile

import requests

from modules.utils.config_loader import RemoteLogDestination, RemoteLogExportSettings

try:  # pragma: no cover - optional dependency
    import paramiko  # type: ignore
except Exception:  # pragma: no cover - resolved lazily in _send_sftp
    paramiko = None  # type: ignore


class RemoteExportError(RuntimeError):
    """Fehler beim Remote Export."""


@dataclass
class RemoteExportResult:
    archive: Path
    files: List[Path]
    successes: List[str]
    failures: Dict[str, str]
    timestamp: datetime
    reason: str
    duration: float

    @property
    def ok(self) -> bool:
        return not self.failures and bool(self.successes)


class RemoteLogExporter:
    """Exportiert Logfiles zu konfigurierten Remote Zielen."""

    def __init__(
        self,
        settings: RemoteLogExportSettings,
        log_path: str | os.PathLike[str],
        logger: Optional[logging.Logger] = None,
        notify: Optional[Callable[[str, bool, Optional[Exception]], None]] = None,
    ) -> None:
        self.settings = settings
        self.log_path = Path(log_path).resolve()
        self.log_dir = self.log_path.parent
        self.logger = logger or logging.getLogger(__name__)
        self.notify_callback = notify
        self.export_dir = Path(settings.staging_dir or (self.log_dir / "exports"))
        self.export_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.last_result: Optional[RemoteExportResult] = None

    # ======== Public API ========

    def export_now(self, reason: str = "manual") -> RemoteExportResult:
        start = time.perf_counter()
        with self._lock:
            files = self._collect_files()
            if not files:
                raise RemoteExportError(
                    f"no log files found in {self.log_dir} matching {self.settings.source_glob}"
                )
            archive = self._create_archive(files)
            successes: List[str] = []
            failures: Dict[str, str] = {}
            for dest in self._destinations_for_cycle():
                identifier = dest.name or dest.type
                try:
                    self._send_to_destination(dest, archive)
                    successes.append(identifier)
                    self._notify(f"Log export to {identifier} completed", True, None)
                except Exception as ex:
                    failures[identifier] = str(ex)
                    self.logger.warning("log export to %s failed: %s", identifier, ex, extra={"source": "logging"})
                    self._notify(f"Log export to {identifier} failed", False, ex)

            self._apply_retention()

            duration = time.perf_counter() - start
            result = RemoteExportResult(
                archive=archive,
                files=files,
                successes=successes,
                failures=failures,
                timestamp=datetime.now(timezone.utc),
                reason=reason,
                duration=duration,
            )
            self.last_result = result
            return result

    def start_periodic_export(
        self,
        interval_minutes: Optional[int] = None,
        *,
        interval_seconds: Optional[float] = None,
    ) -> bool:
        if interval_seconds is None:
            minutes = interval_minutes
            if minutes is None:
                minutes = self.settings.schedule_minutes
            if minutes is None:
                return False
            interval_seconds = float(minutes) * 60.0
        if interval_seconds is None or interval_seconds <= 0:
            return False

        if self._thread and self._thread.is_alive():
            return True

        self._stop_event.clear()
        thread = threading.Thread(
            target=self._run_periodic,
            args=(interval_seconds,),
            name="RemoteLogExporter",
            daemon=True,
        )
        self._thread = thread
        thread.start()
        return True

    def stop_periodic_export(self, timeout: float = 5.0) -> None:
        self._stop_event.set()
        thread = self._thread
        if thread and thread.is_alive():
            thread.join(timeout=timeout)
        self._thread = None

    def shutdown(self) -> None:
        self.stop_periodic_export()

    # ======== Internals ========

    def _run_periodic(self, interval_seconds: float) -> None:
        while not self._stop_event.wait(interval_seconds):
            try:
                self.export_now(reason="scheduled")
            except Exception as ex:  # pragma: no cover - safety log
                self.logger.error("scheduled log export failed: %s", ex, extra={"source": "logging"})

    def _destinations_for_cycle(self) -> Iterable[RemoteLogDestination]:
        for dest in self.settings.destinations:
            if not dest.enabled:
                continue
            yield dest

    def _collect_files(self) -> List[Path]:
        pattern = self.settings.source_glob or "*.log"
        files = sorted(
            (p for p in self.log_dir.glob(pattern) if p.is_file()),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        limit = self.settings.include_history
        if limit is None or limit <= 0:
            return files
        return files[:limit]

    def _create_archive(self, files: List[Path]) -> Path:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        archive_name = f"log_export_{timestamp}.zip"
        archive_path = self.export_dir / archive_name
        compression = ZIP_DEFLATED if self.settings.compress else ZIP_STORED
        with ZipFile(archive_path, "w", compression=compression) as zf:
            for file in files:
                zf.write(file, arcname=file.name)
        return archive_path

    def _send_to_destination(self, dest: RemoteLogDestination, archive: Path) -> None:
        if dest.type == "http":
            self._send_http(dest, archive)
        elif dest.type == "sftp":
            self._send_sftp(dest, archive)
        elif dest.type == "email":
            self._send_email(dest, archive)
        else:
            raise RemoteExportError(f"unknown destination type: {dest.type}")

    def _send_http(self, dest: RemoteLogDestination, archive: Path) -> None:
        if not dest.url:
            raise RemoteExportError("HTTP destination missing 'url'")
        method = (dest.method or "POST").upper()
        headers = dict(dest.headers)
        if dest.token and not any(k.lower() == "authorization" for k in headers):
            headers["Authorization"] = f"Bearer {dest.token}"
        auth = None
        if dest.username and dest.password:
            from requests.auth import HTTPBasicAuth

            auth = HTTPBasicAuth(dest.username, dest.password)
        with archive.open("rb") as fh:
            files = {"file": (archive.name, fh, "application/zip")}
            response = requests.request(
                method,
                dest.url,
                files=files,
                headers=headers,
                verify=dest.verify_tls,
                timeout=dest.timeout or None,
                auth=auth,
            )
            if response.status_code // 100 != 2:
                snippet = (response.text or "")[:200]
                raise RemoteExportError(f"HTTP upload failed with status {response.status_code}: {snippet}")

    def _load_private_key(self, dest: RemoteLogDestination):
        if not dest.private_key:
            return None
        if paramiko is None:
            raise RemoteExportError("paramiko is required for private key authentication")
        loaders = [
            getattr(paramiko, name, None)
            for name in ("RSAKey", "Ed25519Key", "ECDSAKey")
        ]
        last_error: Optional[Exception] = None
        for loader in loaders:
            if loader is None:
                continue
            try:
                return loader.from_private_key_file(dest.private_key, password=dest.passphrase)
            except Exception as ex:  # pragma: no cover - fallback order
                last_error = ex
                continue
        if last_error:
            raise RemoteExportError(f"could not load private key: {last_error}")
        raise RemoteExportError("paramiko does not support private key loader")

    def _send_sftp(self, dest: RemoteLogDestination, archive: Path) -> None:
        if not dest.host:
            raise RemoteExportError("SFTP destination missing 'host'")
        if paramiko is None:
            raise RemoteExportError("paramiko is required for SFTP uploads")
        port = dest.port or 22
        transport = paramiko.Transport((dest.host, port))
        try:
            pkey = self._load_private_key(dest)
            if pkey is not None:
                if not dest.username:
                    raise RemoteExportError("SFTP private key authentication requires username")
                transport.connect(username=dest.username, pkey=pkey)
            else:
                if not dest.username:
                    raise RemoteExportError("SFTP destination requires username")
                if not dest.password:
                    raise RemoteExportError("SFTP password missing and no private key provided")
                transport.connect(username=dest.username, password=dest.password)
            sftp = paramiko.SFTPClient.from_transport(transport)
            try:
                remote_path = dest.remote_path or f"/tmp/{archive.name}"
                sftp.put(str(archive), remote_path)
            finally:
                try:
                    sftp.close()
                except Exception:
                    pass
        finally:
            try:
                transport.close()
            except Exception:
                pass

    def _send_email(self, dest: RemoteLogDestination, archive: Path) -> None:
        recipients = dest.email_to + dest.email_cc + dest.email_bcc
        if not recipients:
            raise RemoteExportError("Email destination requires at least one recipient")
        sender = dest.email_from or (dest.username or "")
        if not sender:
            raise RemoteExportError("Email destination requires 'email_from' or username")
        host = dest.smtp_host or dest.host
        if not host:
            raise RemoteExportError("Email destination missing SMTP host")

        port = dest.smtp_port or dest.port
        if port is None:
            port = 465 if dest.use_ssl else (587 if dest.use_tls else 25)

        msg = EmailMessage()
        msg["Subject"] = dest.subject or "Kiosk Logs"
        msg["From"] = sender
        msg["To"] = ", ".join(dest.email_to)
        if dest.email_cc:
            msg["Cc"] = ", ".join(dest.email_cc)
        msg.set_content(dest.body or "Attached kiosk log export.")
        with archive.open("rb") as fh:
            data = fh.read()
        msg.add_attachment(data, maintype="application", subtype="zip", filename=archive.name)

        smtp_cls = smtplib.SMTP_SSL if dest.use_ssl else smtplib.SMTP
        with smtp_cls(host, port, timeout=dest.timeout or None) as smtp:
            if dest.use_tls and not dest.use_ssl:
                smtp.starttls()
            if dest.username:
                smtp.login(dest.username, dest.password or "")
            smtp.send_message(msg, from_addr=sender, to_addrs=recipients)

    def _apply_retention(self) -> None:
        retention_count = self.settings.retention_count
        if retention_count is not None and retention_count < 0:
            retention_count = None
        retention_days = self.settings.retention_days
        if retention_days is not None and retention_days < 0:
            retention_days = None

        if retention_count is None and retention_days is None:
            return

        archives = sorted(
            (p for p in self.export_dir.glob("log_export_*.zip") if p.is_file()),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        now = datetime.now(timezone.utc)
        for idx, archive in enumerate(archives):
            remove = False
            if retention_count is not None and idx >= retention_count:
                remove = True
            if not remove and retention_days is not None:
                age = now - datetime.utcfromtimestamp(archive.stat().st_mtime)
                if age > timedelta(days=retention_days):
                    remove = True
            if remove:
                try:
                    archive.unlink()
                except FileNotFoundError:
                    pass

    def _notify(self, message: str, success: bool, error: Optional[Exception]) -> None:
        if not self.notify_callback:
            return
        if not success and not self.settings.notify_failures:
            return
        try:
            self.notify_callback(message, success, error)
        except Exception:
            self.logger.debug("notification callback failed", exc_info=True)


import smtplib  # noqa: E402  # isort:skip (after smtplib usage)

