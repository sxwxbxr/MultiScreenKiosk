# modules/ui/remote_export_dialog.py
from __future__ import annotations

from copy import deepcopy
import re
from typing import Dict, List, Optional

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QPlainTextEdit,
    QSpinBox,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from modules.utils.config_loader import RemoteLogDestination, RemoteLogExportSettings
from modules.utils.i18n import tr


def _list_from_text(text: str) -> List[str]:
    parts = re.split(r"[;\n,]", text)
    return [p.strip() for p in parts if p.strip()]


def _headers_from_text(text: str) -> Dict[str, str]:
    headers: Dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if ":" in line:
            key, value = line.split(":", 1)
        elif "=" in line:
            key, value = line.split("=", 1)
        else:
            continue
        headers[key.strip()] = value.strip()
    return headers


def _headers_to_text(headers: Dict[str, str]) -> str:
    return "\n".join(f"{k}: {v}" for k, v in headers.items())


class RemoteExportDialog(QDialog):
    """Dialog zur Konfiguration des Remote Log Exports."""

    def __init__(self, settings: RemoteLogExportSettings, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle(tr("Remote log export"))
        self.setModal(True)
        self.resize(960, 640)

        self._settings = deepcopy(settings)
        self._destinations: List[RemoteLogDestination] = [deepcopy(d) for d in settings.destinations]
        self._updating = False
        self._result: Optional[RemoteLogExportSettings] = None

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(12)

        self.general_box = QGroupBox(tr("General settings"), self)
        general_form = QFormLayout(self.general_box)
        general_form.setLabelAlignment(Qt.AlignLeft)

        self.enabled_cb = QCheckBox(tr("Enable remote export"), self.general_box)
        general_form.addRow(self.enabled_cb)

        self.include_history_spin = QSpinBox(self.general_box)
        self.include_history_spin.setRange(1, 50)
        general_form.addRow(tr("Log files per export"), self.include_history_spin)

        self.compress_cb = QCheckBox(tr("Compress archives (ZIP)"), self.general_box)
        general_form.addRow(self.compress_cb)

        staging_row = QHBoxLayout()
        self.staging_edit = QLineEdit(self.general_box)
        self.staging_edit.setPlaceholderText(tr("Default export folder"))
        self.staging_button = QPushButton(tr("Browse"), self.general_box)
        self.staging_button.clicked.connect(self._browse_staging_dir)
        staging_row.addWidget(self.staging_edit, 1)
        staging_row.addWidget(self.staging_button)
        staging_widget = QWidget(self.general_box)
        staging_widget.setLayout(staging_row)
        general_form.addRow(tr("Staging directory"), staging_widget)

        self.retention_count_spin = QSpinBox(self.general_box)
        self.retention_count_spin.setRange(-1, 365)
        self.retention_count_spin.setSpecialValueText(tr("Keep all archives"))
        general_form.addRow(tr("Retention (archives)"), self.retention_count_spin)

        self.retention_days_spin = QSpinBox(self.general_box)
        self.retention_days_spin.setRange(-1, 3650)
        self.retention_days_spin.setSpecialValueText(tr("No day limit"))
        general_form.addRow(tr("Retention (days)"), self.retention_days_spin)

        self.schedule_spin = QSpinBox(self.general_box)
        self.schedule_spin.setRange(0, 24 * 60)
        self.schedule_spin.setSpecialValueText(tr("Disabled"))
        general_form.addRow(tr("Default schedule (minutes)"), self.schedule_spin)

        self.source_glob_edit = QLineEdit(self.general_box)
        self.source_glob_edit.setPlaceholderText("*.log")
        general_form.addRow(tr("File pattern"), self.source_glob_edit)

        self.notify_failures_cb = QCheckBox(tr("Only notify on failures"), self.general_box)
        general_form.addRow(self.notify_failures_cb)

        main_layout.addWidget(self.general_box)

        self.dest_box = QGroupBox(tr("Destinations"), self)
        dest_layout = QHBoxLayout(self.dest_box)
        dest_layout.setContentsMargins(8, 8, 8, 8)
        dest_layout.setSpacing(12)

        self.dest_list = QListWidget(self.dest_box)
        self.dest_list.currentRowChanged.connect(self._on_dest_selected)
        dest_layout.addWidget(self.dest_list, 1)

        button_col = QVBoxLayout()
        self.btn_add = QPushButton(tr("Add"), self.dest_box)
        self.btn_add.clicked.connect(self._add_destination)
        self.btn_remove = QPushButton(tr("Remove"), self.dest_box)
        self.btn_remove.clicked.connect(self._remove_destination)
        self.btn_duplicate = QPushButton(tr("Duplicate"), self.dest_box)
        self.btn_duplicate.clicked.connect(self._duplicate_destination)
        self.btn_up = QPushButton(tr("Up"), self.dest_box)
        self.btn_up.clicked.connect(lambda: self._move_destination(-1))
        self.btn_down = QPushButton(tr("Down"), self.dest_box)
        self.btn_down.clicked.connect(lambda: self._move_destination(+1))
        for btn in (self.btn_add, self.btn_remove, self.btn_duplicate, self.btn_up, self.btn_down):
            button_col.addWidget(btn)
        button_col.addStretch(1)
        dest_layout.addLayout(button_col)

        self.detail_box = QGroupBox(tr("Destination details"), self.dest_box)
        self.detail_form = QFormLayout(self.detail_box)
        self.detail_form.setLabelAlignment(Qt.AlignLeft)

        self.dest_enabled_cb = QCheckBox(tr("Destination enabled"), self.detail_box)
        self.detail_form.addRow(self.dest_enabled_cb)

        self.dest_name_edit = QLineEdit(self.detail_box)
        self.detail_form.addRow(tr("Display name"), self.dest_name_edit)

        self.dest_type_combo = QComboBox(self.detail_box)
        self.dest_type_combo.addItem(tr("HTTP upload"), "http")
        self.dest_type_combo.addItem(tr("SFTP upload"), "sftp")
        self.dest_type_combo.addItem(tr("Email delivery"), "email")
        self.detail_form.addRow(tr("Destination type"), self.dest_type_combo)

        self.dest_schedule_spin = QSpinBox(self.detail_box)
        self.dest_schedule_spin.setRange(0, 24 * 60)
        self.dest_schedule_spin.setSpecialValueText(tr("Use global schedule"))
        self.detail_form.addRow(tr("Schedule override (minutes)"), self.dest_schedule_spin)

        self.dest_timeout_spin = QSpinBox(self.detail_box)
        self.dest_timeout_spin.setRange(0, 600)
        self.dest_timeout_spin.setSpecialValueText(tr("Use default"))
        self.detail_form.addRow(tr("Timeout (seconds)"), self.dest_timeout_spin)

        self.type_stack = QStackedWidget(self.detail_box)
        self._build_http_page()
        self._build_sftp_page()
        self._build_email_page()
        self.detail_form.addRow(self.type_stack)

        dest_layout.addWidget(self.detail_box, 2)
        main_layout.addWidget(self.dest_box, 1)

        footer = QHBoxLayout()
        footer.addStretch(1)
        self.btn_cancel = QPushButton(tr("Cancel"), self)
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_ok = QPushButton(tr("Save"), self)
        self.btn_ok.clicked.connect(self.accept)
        footer.addWidget(self.btn_cancel)
        footer.addWidget(self.btn_ok)
        main_layout.addLayout(footer)

        self._connect_detail_signals()
        self._apply_general_settings_to_widgets()
        self._refresh_dest_list()

        if self._destinations:
            self.dest_list.setCurrentRow(0)
        else:
            self._update_detail_enabled()

    # ---------- Aufbau Unterseiten ----------

    def _build_http_page(self) -> None:
        self.http_page = QWidget(self.type_stack)
        form = QFormLayout(self.http_page)
        self.http_url_edit = QLineEdit(self.http_page)
        form.addRow(tr("URL"), self.http_url_edit)
        self.http_method_edit = QLineEdit(self.http_page)
        self.http_method_edit.setPlaceholderText("POST")
        form.addRow(tr("HTTP method"), self.http_method_edit)
        self.http_verify_cb = QCheckBox(tr("Verify TLS certificates"), self.http_page)
        form.addRow(self.http_verify_cb)
        self.http_headers_edit = QPlainTextEdit(self.http_page)
        self.http_headers_edit.setPlaceholderText(tr("Header lines: Key: Value"))
        form.addRow(tr("Custom headers"), self.http_headers_edit)
        self.http_token_edit = QLineEdit(self.http_page)
        form.addRow(tr("Bearer token"), self.http_token_edit)
        self.http_username_edit = QLineEdit(self.http_page)
        form.addRow(tr("Username"), self.http_username_edit)
        self.http_password_edit = QLineEdit(self.http_page)
        self.http_password_edit.setEchoMode(QLineEdit.Password)
        form.addRow(tr("Password"), self.http_password_edit)
        self.type_stack.addWidget(self.http_page)

    def _build_sftp_page(self) -> None:
        self.sftp_page = QWidget(self.type_stack)
        form = QFormLayout(self.sftp_page)
        self.sftp_host_edit = QLineEdit(self.sftp_page)
        form.addRow(tr("Host"), self.sftp_host_edit)
        self.sftp_port_spin = QSpinBox(self.sftp_page)
        self.sftp_port_spin.setRange(0, 65535)
        self.sftp_port_spin.setSpecialValueText(tr("Default"))
        form.addRow(tr("Port"), self.sftp_port_spin)
        self.sftp_username_edit = QLineEdit(self.sftp_page)
        form.addRow(tr("Username"), self.sftp_username_edit)
        self.sftp_password_edit = QLineEdit(self.sftp_page)
        self.sftp_password_edit.setEchoMode(QLineEdit.Password)
        form.addRow(tr("Password"), self.sftp_password_edit)
        self.sftp_remote_path_edit = QLineEdit(self.sftp_page)
        self.sftp_remote_path_edit.setPlaceholderText("/tmp/logs.zip")
        form.addRow(tr("Remote path"), self.sftp_remote_path_edit)
        self.sftp_private_key_edit = QLineEdit(self.sftp_page)
        form.addRow(tr("Private key file"), self.sftp_private_key_edit)
        self.sftp_passphrase_edit = QLineEdit(self.sftp_page)
        self.sftp_passphrase_edit.setEchoMode(QLineEdit.Password)
        form.addRow(tr("Key passphrase"), self.sftp_passphrase_edit)
        self.type_stack.addWidget(self.sftp_page)

    def _build_email_page(self) -> None:
        self.email_page = QWidget(self.type_stack)
        form = QFormLayout(self.email_page)
        self.email_from_edit = QLineEdit(self.email_page)
        form.addRow(tr("Sender address"), self.email_from_edit)
        self.email_to_edit = QLineEdit(self.email_page)
        form.addRow(tr("To"), self.email_to_edit)
        self.email_cc_edit = QLineEdit(self.email_page)
        form.addRow(tr("Cc"), self.email_cc_edit)
        self.email_bcc_edit = QLineEdit(self.email_page)
        form.addRow(tr("Bcc"), self.email_bcc_edit)
        self.email_smtp_host_edit = QLineEdit(self.email_page)
        form.addRow(tr("SMTP host"), self.email_smtp_host_edit)
        self.email_smtp_port_spin = QSpinBox(self.email_page)
        self.email_smtp_port_spin.setRange(0, 65535)
        self.email_smtp_port_spin.setSpecialValueText(tr("Auto"))
        form.addRow(tr("SMTP port"), self.email_smtp_port_spin)
        self.email_username_edit = QLineEdit(self.email_page)
        form.addRow(tr("Username"), self.email_username_edit)
        self.email_password_edit = QLineEdit(self.email_page)
        self.email_password_edit.setEchoMode(QLineEdit.Password)
        form.addRow(tr("Password"), self.email_password_edit)
        self.email_use_tls_cb = QCheckBox(tr("Use STARTTLS"), self.email_page)
        form.addRow(self.email_use_tls_cb)
        self.email_use_ssl_cb = QCheckBox(tr("Use SSL"), self.email_page)
        form.addRow(self.email_use_ssl_cb)
        self.email_subject_edit = QLineEdit(self.email_page)
        form.addRow(tr("Subject"), self.email_subject_edit)
        self.email_body_edit = QTextEdit(self.email_page)
        self.email_body_edit.setPlaceholderText(tr("Message body"))
        self.email_body_edit.setAcceptRichText(False)
        form.addRow(tr("Body"), self.email_body_edit)
        self.type_stack.addWidget(self.email_page)

    # ---------- Signalverkettung ----------

    def _connect_detail_signals(self) -> None:
        self.dest_enabled_cb.toggled.connect(lambda state: self._update_dest_attr("enabled", bool(state)))
        self.dest_name_edit.textChanged.connect(lambda text: self._update_dest_attr("name", text.strip()))
        self.dest_type_combo.currentIndexChanged.connect(self._on_dest_type_changed)
        self.dest_schedule_spin.valueChanged.connect(self._on_dest_schedule_changed)
        self.dest_timeout_spin.valueChanged.connect(lambda value: self._update_dest_attr("timeout", int(value)))

        self.http_url_edit.textChanged.connect(lambda text: self._update_dest_attr("url", text.strip() or None))
        self.http_method_edit.textChanged.connect(lambda text: self._update_dest_attr("method", text.strip() or "POST"))
        self.http_verify_cb.toggled.connect(lambda state: self._update_dest_attr("verify_tls", bool(state)))
        self.http_headers_edit.textChanged.connect(self._on_headers_changed)
        self.http_token_edit.textChanged.connect(lambda text: self._update_dest_attr("token", text.strip() or None))
        self.http_username_edit.textChanged.connect(lambda text: self._update_dest_attr("username", text.strip() or None))
        self.http_password_edit.textChanged.connect(lambda text: self._update_dest_attr("password", text))

        self.sftp_host_edit.textChanged.connect(lambda text: self._update_dest_attr("host", text.strip() or None))
        self.sftp_port_spin.valueChanged.connect(self._on_sftp_port_changed)
        self.sftp_username_edit.textChanged.connect(lambda text: self._update_dest_attr("username", text.strip() or None))
        self.sftp_password_edit.textChanged.connect(lambda text: self._update_dest_attr("password", text))
        self.sftp_remote_path_edit.textChanged.connect(lambda text: self._update_dest_attr("remote_path", text.strip() or None))
        self.sftp_private_key_edit.textChanged.connect(lambda text: self._update_dest_attr("private_key", text.strip() or None))
        self.sftp_passphrase_edit.textChanged.connect(lambda text: self._update_dest_attr("passphrase", text or None))

        self.email_from_edit.textChanged.connect(lambda text: self._update_dest_attr("email_from", text.strip() or None))
        self.email_to_edit.textChanged.connect(lambda text: self._update_dest_attr("email_to", _list_from_text(text)))
        self.email_cc_edit.textChanged.connect(lambda text: self._update_dest_attr("email_cc", _list_from_text(text)))
        self.email_bcc_edit.textChanged.connect(lambda text: self._update_dest_attr("email_bcc", _list_from_text(text)))
        self.email_smtp_host_edit.textChanged.connect(lambda text: self._update_dest_attr("smtp_host", text.strip() or None))
        self.email_smtp_port_spin.valueChanged.connect(self._on_email_port_changed)
        self.email_username_edit.textChanged.connect(lambda text: self._update_dest_attr("username", text.strip() or None))
        self.email_password_edit.textChanged.connect(lambda text: self._update_dest_attr("password", text))
        self.email_use_tls_cb.toggled.connect(lambda state: self._update_dest_attr("use_tls", bool(state)))
        self.email_use_ssl_cb.toggled.connect(lambda state: self._update_dest_attr("use_ssl", bool(state)))
        self.email_subject_edit.textChanged.connect(lambda text: self._update_dest_attr("subject", text.strip() or None))
        self.email_body_edit.textChanged.connect(self._on_email_body_changed)

    # ---------- Allgemeine Einstellungen ----------

    def _apply_general_settings_to_widgets(self) -> None:
        self.enabled_cb.setChecked(self._settings.enabled)
        self.include_history_spin.setValue(max(1, self._settings.include_history))
        self.compress_cb.setChecked(self._settings.compress)
        self.staging_edit.setText(self._settings.staging_dir or "")
        retention_count = self._settings.retention_count
        if retention_count is None:
            self.retention_count_spin.setValue(-1)
        else:
            self.retention_count_spin.setValue(retention_count)
        retention_days = self._settings.retention_days
        if retention_days is None:
            self.retention_days_spin.setValue(-1)
        else:
            self.retention_days_spin.setValue(retention_days)
        self.schedule_spin.setValue(self._settings.schedule_minutes or 0)
        self.source_glob_edit.setText(self._settings.source_glob or "*.log")
        self.notify_failures_cb.setChecked(self._settings.notify_failures)

    def _apply_general_widgets_to_settings(self) -> None:
        self._settings.enabled = bool(self.enabled_cb.isChecked())
        self._settings.include_history = int(self.include_history_spin.value())
        self._settings.compress = bool(self.compress_cb.isChecked())
        staging = self.staging_edit.text().strip()
        self._settings.staging_dir = staging or None
        rc_val = self.retention_count_spin.value()
        self._settings.retention_count = None if rc_val < 0 else rc_val
        rd_val = self.retention_days_spin.value()
        self._settings.retention_days = None if rd_val < 0 else rd_val
        sched = self.schedule_spin.value()
        self._settings.schedule_minutes = None if sched <= 0 else sched
        self._settings.source_glob = self.source_glob_edit.text().strip() or "*.log"
        self._settings.notify_failures = bool(self.notify_failures_cb.isChecked())

    # ---------- Destination Verwaltung ----------

    def _refresh_dest_list(self) -> None:
        self.dest_list.blockSignals(True)
        current = self.dest_list.currentRow()
        self.dest_list.clear()
        for dest in self._destinations:
            label = dest.name or dest.type
            if not dest.enabled:
                label = f"{label} ({tr('disabled')})"
            item = QListWidgetItem(label)
            self.dest_list.addItem(item)
        self.dest_list.blockSignals(False)
        if self._destinations and 0 <= current < len(self._destinations):
            self.dest_list.setCurrentRow(current)
        elif self._destinations:
            self.dest_list.setCurrentRow(0)
        self._update_detail_enabled()

    def _update_detail_enabled(self) -> None:
        has_dest = bool(self._destinations and 0 <= self.dest_list.currentRow() < len(self._destinations))
        self.detail_box.setEnabled(has_dest)
        self.btn_remove.setEnabled(has_dest)
        self.btn_duplicate.setEnabled(has_dest)
        self.btn_up.setEnabled(has_dest and self.dest_list.currentRow() > 0)
        self.btn_down.setEnabled(has_dest and self.dest_list.currentRow() < len(self._destinations) - 1)

    def _add_destination(self) -> None:
        dest = RemoteLogDestination()
        dest.name = tr("Destination {index}", index=len(self._destinations) + 1)
        self._destinations.append(dest)
        self._refresh_dest_list()
        self.dest_list.setCurrentRow(len(self._destinations) - 1)

    def _remove_destination(self) -> None:
        row = self.dest_list.currentRow()
        if 0 <= row < len(self._destinations):
            del self._destinations[row]
            self._refresh_dest_list()

    def _duplicate_destination(self) -> None:
        row = self.dest_list.currentRow()
        if 0 <= row < len(self._destinations):
            clone = deepcopy(self._destinations[row])
            clone.name = f"{clone.name or clone.type} ({tr('copy')})"
            self._destinations.insert(row + 1, clone)
            self._refresh_dest_list()
            self.dest_list.setCurrentRow(row + 1)

    def _move_destination(self, delta: int) -> None:
        row = self.dest_list.currentRow()
        new_row = row + delta
        if 0 <= row < len(self._destinations) and 0 <= new_row < len(self._destinations):
            self._destinations[row], self._destinations[new_row] = (
                self._destinations[new_row],
                self._destinations[row],
            )
            self._refresh_dest_list()
            self.dest_list.setCurrentRow(new_row)

    def _on_dest_selected(self, index: int) -> None:
        if not (0 <= index < len(self._destinations)):
            self._update_detail_enabled()
            return
        self._updating = True
        dest = self._destinations[index]
        self.dest_enabled_cb.setChecked(dest.enabled)
        self.dest_name_edit.setText(dest.name or "")
        type_index = max(0, self.dest_type_combo.findData(dest.type or "http"))
        self.dest_type_combo.setCurrentIndex(type_index)
        self.dest_schedule_spin.setValue(dest.schedule_minutes or 0)
        self.dest_timeout_spin.setValue(dest.timeout or 0)
        self._load_http_fields(dest)
        self._load_sftp_fields(dest)
        self._load_email_fields(dest)
        self._apply_type_visibility(dest.type or "http")
        self._updating = False
        self._update_detail_enabled()

    def _load_http_fields(self, dest: RemoteLogDestination) -> None:
        self.http_url_edit.setText(dest.url or "")
        self.http_method_edit.setText(dest.method or "POST")
        self.http_verify_cb.setChecked(dest.verify_tls)
        self.http_headers_edit.setPlainText(_headers_to_text(dest.headers or {}))
        self.http_token_edit.setText(dest.token or "")
        self.http_username_edit.setText(dest.username or "")
        self.http_password_edit.setText(dest.password or "")

    def _load_sftp_fields(self, dest: RemoteLogDestination) -> None:
        self.sftp_host_edit.setText(dest.host or "")
        self.sftp_port_spin.setValue(dest.port or 0)
        self.sftp_username_edit.setText(dest.username or "")
        self.sftp_password_edit.setText(dest.password or "")
        self.sftp_remote_path_edit.setText(dest.remote_path or "")
        self.sftp_private_key_edit.setText(dest.private_key or "")
        self.sftp_passphrase_edit.setText(dest.passphrase or "")

    def _load_email_fields(self, dest: RemoteLogDestination) -> None:
        self.email_from_edit.setText(dest.email_from or "")
        self.email_to_edit.setText(", ".join(dest.email_to) if dest.email_to else "")
        self.email_cc_edit.setText(", ".join(dest.email_cc) if dest.email_cc else "")
        self.email_bcc_edit.setText(", ".join(dest.email_bcc) if dest.email_bcc else "")
        self.email_smtp_host_edit.setText(dest.smtp_host or dest.host or "")
        self.email_smtp_port_spin.setValue(dest.smtp_port or dest.port or 0)
        self.email_username_edit.setText(dest.username or "")
        self.email_password_edit.setText(dest.password or "")
        self.email_use_tls_cb.setChecked(dest.use_tls)
        self.email_use_ssl_cb.setChecked(dest.use_ssl)
        self.email_subject_edit.setText(dest.subject or "")
        self.email_body_edit.setPlainText(dest.body or "")

    def _update_dest_attr(self, attr: str, value) -> None:
        if self._updating:
            return
        row = self.dest_list.currentRow()
        if not (0 <= row < len(self._destinations)):
            return
        dest = self._destinations[row]
        setattr(dest, attr, value)
        if attr in {"name", "enabled", "type"}:
            self._refresh_dest_list()

    def _apply_type_visibility(self, type_code: str) -> None:
        mapping = {"http": 0, "sftp": 1, "email": 2}
        self.type_stack.setCurrentIndex(mapping.get(type_code, 0))

    def _on_dest_type_changed(self, _index: int) -> None:
        type_code = self.dest_type_combo.currentData()
        self._apply_type_visibility(type_code)
        if not self._updating:
            self._update_dest_attr("type", type_code)

    def _on_dest_schedule_changed(self, value: int) -> None:
        minutes = None if value <= 0 else int(value)
        self._update_dest_attr("schedule_minutes", minutes)

    def _on_headers_changed(self) -> None:
        if self._updating:
            return
        headers = _headers_from_text(self.http_headers_edit.toPlainText())
        self._update_dest_attr("headers", headers)

    def _on_sftp_port_changed(self, value: int) -> None:
        self._update_dest_attr("port", None if value <= 0 else int(value))

    def _on_email_port_changed(self, value: int) -> None:
        port = None if value <= 0 else int(value)
        self._update_dest_attr("smtp_port", port)
        self._update_dest_attr("port", port)

    def _on_email_body_changed(self) -> None:
        if self._updating:
            return
        self._update_dest_attr("body", self.email_body_edit.toPlainText())

    # ---------- Helpers ----------

    def _browse_staging_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(self, tr("Select directory"))
        if path:
            self.staging_edit.setText(path)

    # ---------- QDialog Overrides ----------

    def accept(self) -> None:  # type: ignore[override]
        self._apply_general_widgets_to_settings()
        self._settings.destinations = [deepcopy(d) for d in self._destinations]
        self._result = self._settings
        super().accept()

    # ---------- Public API ----------

    def result_settings(self) -> Optional[RemoteLogExportSettings]:
        return self._result
