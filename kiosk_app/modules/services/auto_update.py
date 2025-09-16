"""Automatic update service for MultiScreenKiosk."""

from __future__ import annotations

import contextlib
import hashlib
import logging
import os
import shutil
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Optional
from urllib.parse import urlparse
from zipfile import BadZipFile, ZipFile

import requests

from modules.utils.config_loader import UpdateSettings

try:  # pragma: no cover - optional dependency
    from packaging.version import Version as _PkgVersion  # type: ignore
except Exception:  # pragma: no cover - dependency is optional
    _PkgVersion = None  # type: ignore


class UpdateError(RuntimeError):
    """Raised when the update process fails."""

    def __init__(self, message: str, *, rolled_back: bool = False):
        super().__init__(message)
        self.rolled_back = rolled_back


@dataclass
class UpdateRelease:
    version: str
    channel: str
    url: str
    sha256: str
    size: Optional[int] = None
    notes: Optional[str] = None
    mandatory: bool = False


@dataclass
class UpdateResult:
    release: Optional[UpdateRelease]
    downloaded_to: Optional[Path] = None
    installed: bool = False
    restart_required: bool = False
    error: Optional[str] = None
    rolled_back: bool = False


class AutoUpdateService:
    """Checks a release feed, downloads and installs updates."""

    FEED_TIMEOUT = 10
    DOWNLOAD_TIMEOUT = 30

    def __init__(
        self,
        settings: UpdateSettings,
        install_dir: Path | str,
        current_version: str,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self.settings = settings
        self.install_dir = Path(install_dir).resolve()
        self.install_dir.mkdir(parents=True, exist_ok=True)
        download_dir = settings.download_dir or str(self.install_dir / "updates")
        self.download_dir = Path(download_dir).resolve()
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self.current_version = current_version
        self.log = logger or logging.getLogger(__name__)
        self._thread: Optional[threading.Thread] = None

    # ===== Public API ==================================================
    def run_once(self) -> Optional[UpdateResult]:
        """Checks for updates and installs one if available."""

        if not self.settings.enabled:
            self.log.debug("auto update disabled in config", extra={"source": "update"})
            return None
        feed_url = (self.settings.feed_url or "").strip()
        if not feed_url:
            self.log.debug("auto update feed url missing", extra={"source": "update"})
            return None

        try:
            release = self.check_for_update()
        except UpdateError as ex:
            self.log.warning("update check failed: %s", ex, extra={"source": "update"})
            return UpdateResult(release=None, error=str(ex))

        if not release:
            return None

        if not self.settings.auto_install:
            self.log.info(
                "update %s available but auto install disabled", release.version,
                extra={"source": "update"},
            )
            return UpdateResult(release=release, installed=False, restart_required=False)

        try:
            package_path = self.download_release(release)
            self.verify_package(package_path, release.sha256)
            self.install_package(package_path, release)
        except UpdateError as ex:
            self.log.error("update to %s failed: %s", release.version, ex, extra={"source": "update"})
            return UpdateResult(
                release=release,
                downloaded_to=None,
                installed=False,
                restart_required=False,
                error=str(ex),
                rolled_back=getattr(ex, "rolled_back", False),
            )

        self.log.info("update to %s installed", release.version, extra={"source": "update"})
        return UpdateResult(
            release=release,
            downloaded_to=package_path,
            installed=True,
            restart_required=True,
        )

    def run_in_background(self, callback: Optional[Callable[[Optional[UpdateResult]], None]] = None) -> None:
        """Runs :meth:`run_once` on a background thread."""

        if self._thread and self._thread.is_alive():
            return

        def _target() -> None:
            try:
                result = self.run_once()
            except Exception as ex:  # pragma: no cover - safety net
                self.log.exception("auto update background execution failed: %s", ex)
                result = UpdateResult(release=None, error=str(ex))
            if callback:
                try:
                    callback(result)
                except Exception:  # pragma: no cover - callback errors shouldn't crash thread
                    self.log.exception("auto update callback raised")

        thread = threading.Thread(target=_target, name="AutoUpdateService", daemon=True)
        self._thread = thread
        thread.start()

    # ===== High level operations ======================================
    def check_for_update(self) -> Optional[UpdateRelease]:
        feed = self._fetch_feed()
        release = self._select_release(feed)
        if release is None:
            return None
        if self._compare_versions(release.version, self.current_version) <= 0:
            return None
        return release

    def download_release(self, release: UpdateRelease) -> Path:
        file_name = self._filename_for_release(release)
        target = self.download_dir / file_name
        temp = target.with_suffix(target.suffix + ".part")

        response = None
        try:
            response = requests.get(
                release.url,
                stream=True,
                timeout=self.DOWNLOAD_TIMEOUT,
                verify=self.settings.verify_tls,
            )
        except Exception as ex:
            raise UpdateError(f"failed to download update package: {ex}") from ex

        try:
            if response.status_code >= 400:
                raise UpdateError(f"download returned status {response.status_code}")

            temp.parent.mkdir(parents=True, exist_ok=True)
            with temp.open("wb") as handle:
                for chunk in response.iter_content(chunk_size=65536):
                    if chunk:
                        handle.write(chunk)
            temp.replace(target)
        except Exception as ex:
            with contextlib.suppress(Exception):
                temp.unlink()
            if isinstance(ex, UpdateError):
                raise
            raise UpdateError(f"failed to save update package: {ex}") from ex
        finally:
            if response is not None:
                with contextlib.suppress(Exception):
                    response.close()

        return target

    def verify_package(self, package_path: Path, expected_hash: str) -> None:
        if not expected_hash:
            return
        if not package_path.exists():
            raise UpdateError("downloaded package missing for verification")
        digest = hashlib.sha256()
        with package_path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(65536), b""):
                digest.update(chunk)
        computed = digest.hexdigest().lower()
        if computed != expected_hash.lower():
            raise UpdateError("package verification failed")

    def install_package(self, package_path: Path, release: UpdateRelease) -> None:
        if not package_path.exists():
            raise UpdateError("package path not found for installation")

        backup_dir = self.install_dir / ".update_backup"
        work_dir = self.download_dir / ".update_unpack"
        self._cleanup_dir(work_dir)
        self._cleanup_dir(backup_dir)

        try:
            self._create_backup(backup_dir)
            extracted = self._extract_package(package_path, work_dir)
            self._apply_update(extracted)
        except Exception as ex:
            self.log.warning("update installation failed: %s", ex, extra={"source": "update"})
            try:
                self._rollback(backup_dir)
            except Exception as rollback_ex:
                self.log.error("update rollback failed: %s", rollback_ex, extra={"source": "update"})
                raise UpdateError(
                    f"installation failed and rollback failed: {ex}", rolled_back=False
                ) from rollback_ex
            raise UpdateError(f"installation failed: {ex}", rolled_back=True) from ex
        finally:
            self._cleanup_dir(work_dir)

        self._cleanup_dir(backup_dir)

    # ===== Feed parsing =================================================
    def _fetch_feed(self) -> Dict[str, Any]:
        response = None
        try:
            response = requests.get(
                self.settings.feed_url,
                timeout=self.FEED_TIMEOUT,
                verify=self.settings.verify_tls,
            )
        except Exception as ex:
            raise UpdateError(f"failed to fetch release feed: {ex}") from ex

        try:
            if response.status_code >= 400:
                raise UpdateError(f"release feed returned status {response.status_code}")

            data = response.json()
        except ValueError as ex:
            raise UpdateError(f"release feed is not valid JSON: {ex}") from ex
        finally:
            if response is not None:
                with contextlib.suppress(Exception):
                    response.close()

        if not isinstance(data, dict):
            raise UpdateError("release feed must be a JSON object")

        return data

    def _select_release(self, feed: Dict[str, Any]) -> Optional[UpdateRelease]:
        channel = (self.settings.channel or feed.get("channel") or "stable").lower()

        releases = feed.get("releases")
        entries: list[Dict[str, Any]]
        if isinstance(releases, list):
            entries = [entry for entry in releases if isinstance(entry, dict)]
        elif isinstance(releases, dict):
            entries = [releases]
        else:
            entries = [feed]

        best: Optional[UpdateRelease] = None
        for entry in entries:
            candidate = self._release_from_dict(entry, default_channel=feed.get("channel"))
            if candidate is None:
                continue
            if candidate.channel.lower() != channel:
                continue
            if best is None or self._compare_versions(candidate.version, best.version) > 0:
                best = candidate
        return best

    def _release_from_dict(
        self,
        entry: Dict[str, Any],
        *,
        default_channel: Optional[str] = None,
    ) -> Optional[UpdateRelease]:
        version = self._safe_str(entry.get("version") or entry.get("name"))
        if not version:
            return None

        channel = self._safe_str(entry.get("channel") or default_channel or "stable").lower()
        package = entry.get("package")
        url = self._safe_str(entry.get("url"))
        sha256 = self._safe_str(entry.get("sha256"))
        size_value = entry.get("size")
        if isinstance(package, dict):
            url = self._safe_str(package.get("url") or url)
            sha256 = self._safe_str(package.get("sha256") or sha256)
            size_value = package.get("size", size_value)

        if not url or not sha256:
            return None

        try:
            size = int(size_value) if size_value is not None else None
        except Exception:
            size = None

        notes_val = entry.get("notes") or entry.get("changelog")
        notes = str(notes_val) if notes_val is not None else None

        return UpdateRelease(
            version=version,
            channel=channel,
            url=url,
            sha256=sha256,
            size=size,
            notes=notes,
            mandatory=bool(entry.get("mandatory", False)),
        )

    # ===== Helpers ======================================================
    def _filename_for_release(self, release: UpdateRelease) -> str:
        parsed = urlparse(release.url)
        name = os.path.basename(parsed.path)
        if not name:
            name = f"update_{release.version}.bin"
        return name

    def _create_backup(self, backup_dir: Path) -> None:
        ignore = []
        if self.download_dir.is_relative_to(self.install_dir):  # type: ignore[attr-defined]
            ignore.append(self.download_dir.relative_to(self.install_dir).parts[0])
        ignore.append(backup_dir.name)
        shutil.copytree(
            self.install_dir,
            backup_dir,
            dirs_exist_ok=False,
            ignore=shutil.ignore_patterns(*ignore) if ignore else None,
        )

    def _extract_package(self, package_path: Path, target_dir: Path) -> Path:
        target_dir.mkdir(parents=True, exist_ok=True)
        try:
            with ZipFile(package_path, "r") as archive:
                archive.extractall(target_dir)
        except BadZipFile as ex:
            raise UpdateError(f"package is not a valid zip archive: {ex}") from ex
        return target_dir

    def _apply_update(self, source_dir: Path) -> None:
        for root, _dirs, files in os.walk(source_dir):
            rel = Path(root).relative_to(source_dir)
            dest_dir = self.install_dir / rel
            dest_dir.mkdir(parents=True, exist_ok=True)
            for file_name in files:
                src = Path(root) / file_name
                dst = dest_dir / file_name
                shutil.copy2(src, dst)

    def _rollback(self, backup_dir: Path) -> None:
        if not backup_dir.exists():
            raise UpdateError("no backup available for rollback")

        keep = {backup_dir.name}
        if self.download_dir.is_relative_to(self.install_dir):  # type: ignore[attr-defined]
            keep.add(self.download_dir.relative_to(self.install_dir).parts[0])

        self._clear_install_dir(keep=keep)
        for item in backup_dir.iterdir():
            target = self.install_dir / item.name
            if item.is_dir():
                shutil.copytree(item, target, dirs_exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item, target)

        self._cleanup_dir(backup_dir)

    def _clear_install_dir(self, keep: set[str]) -> None:
        for entry in self.install_dir.iterdir():
            if entry.name in keep:
                continue
            if entry.is_dir():
                shutil.rmtree(entry)
            else:
                entry.unlink()

    def _cleanup_dir(self, path: Path) -> None:
        if path.is_dir():
            shutil.rmtree(path)
        elif path.exists():
            path.unlink()

    @staticmethod
    def _safe_str(value: Any) -> str:
        try:
            return ("" if value is None else str(value)).strip()
        except Exception:
            return ""

    @staticmethod
    def _normalize_version(value: str):
        if _PkgVersion is not None:
            try:
                return _PkgVersion(value)
            except Exception:
                pass
        parts: list[Any] = []
        for part in value.replace("-", ".").split("."):
            if not part:
                continue
            if part.isdigit():
                parts.append(int(part))
            else:
                parts.append(part.lower())
        return tuple(parts)

    def _compare_versions(self, left: str, right: str) -> int:
        a = self._normalize_version(left)
        b = self._normalize_version(right)
        if a == b:
            return 0
        return 1 if a > b else -1


__all__ = [
    "AutoUpdateService",
    "UpdateError",
    "UpdateRelease",
    "UpdateResult",
]

