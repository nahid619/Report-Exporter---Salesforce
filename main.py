# main.py
# Universal Salesforce Report Exporter - Works on ANY org without Connected App
import sys
import threading
import traceback
import datetime
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QFileDialog, QLabel, QProgressBar, QTextEdit, QMessageBox,
    QLineEdit, QComboBox, QGroupBox, QFormLayout, QCheckBox
)
from PySide6.QtCore import Signal, Slot, QObject
from salesforce_auth import SalesforceAuth
from exporter import SalesforceReportExporter


class WorkerSignals(QObject):
    """Signals for thread-safe UI updates"""
    progress = Signal(int, int)
    log = Signal(str)
    finished = Signal(dict)
    error = Signal(str)
    login_success = Signal(dict)
    login_error = Signal(str)


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Salesforce Reports Exporter")
        self.resize(650, 580)
        self.signals = WorkerSignals()
        self._connect_signals()
        self._setup_ui()
        self.session_info = None
        self.output_zip = None
        self._export_running = False

    def _connect_signals(self):
        self.signals.progress.connect(self._on_progress)
        self.signals.log.connect(self._on_log)
        self.signals.finished.connect(self._on_export_finished)
        self.signals.error.connect(self._on_export_error)
        self.signals.login_success.connect(self._on_login_success)
        self.signals.login_error.connect(self._on_login_error)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # Header
        header = QLabel("Salesforce Report Exporter")
        header.setStyleSheet("font-size: 16px; font-weight: bold; padding: 5px;")
        layout.addWidget(header)

        subtitle = QLabel("Export all reports to a single ZIP file. Works on any org!")
        subtitle.setStyleSheet("color: #666; padding-bottom: 10px;")
        layout.addWidget(subtitle)

        # === LOGIN SECTION ===
        login_group = QGroupBox("1. Salesforce Login")
        login_layout = QFormLayout()
        login_layout.setSpacing(8)

        # Environment selector
        env_layout = QHBoxLayout()
        self.env_combo = QComboBox()
        self.env_combo.addItem("Production", "login")
        self.env_combo.addItem("Sandbox", "test")
        env_layout.addWidget(self.env_combo)
        env_layout.addStretch()
        login_layout.addRow("Environment:", env_layout)

        # Custom domain
        domain_layout = QHBoxLayout()
        self.custom_domain_check = QCheckBox()
        self.custom_domain_input = QLineEdit()
        self.custom_domain_input.setPlaceholderText("mycompany.my.salesforce.com")
        self.custom_domain_input.setEnabled(False)
        self.custom_domain_check.toggled.connect(self._on_custom_domain_toggle)
        domain_layout.addWidget(self.custom_domain_check)
        domain_layout.addWidget(self.custom_domain_input, 1)
        login_layout.addRow("Custom Domain:", domain_layout)

        # Username
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("your.email@company.com")
        login_layout.addRow("Username:", self.username_input)

        # Password
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setPlaceholderText("Your Salesforce password")
        login_layout.addRow("Password:", self.password_input)

        # Security Token
        self.token_input = QLineEdit()
        self.token_input.setEchoMode(QLineEdit.Password)
        self.token_input.setPlaceholderText("From email (leave blank if IP whitelisted)")
        login_layout.addRow("Security Token:", self.token_input)

        # Login button
        self.login_btn = QPushButton("Login")
        self.login_btn.setMinimumHeight(32)
        self.login_btn.clicked.connect(self.on_login)
        login_layout.addRow("", self.login_btn)

        # Status label
        self.status_label = QLabel("Not logged in")
        self.status_label.setStyleSheet("color: #888;")
        login_layout.addRow("Status:", self.status_label)

        login_group.setLayout(login_layout)
        layout.addWidget(login_group)

        # === OUTPUT SECTION ===
        output_group = QGroupBox("2. Output Location")
        output_layout = QHBoxLayout()
        self.path_label = QLabel("No file selected")
        self.path_label.setStyleSheet("color: #888;")
        self.path_label.setWordWrap(True)
        output_layout.addWidget(self.path_label, 1)
        self.choose_btn = QPushButton("Browse...")
        self.choose_btn.clicked.connect(self.choose_path)
        output_layout.addWidget(self.choose_btn)
        output_group.setLayout(output_layout)
        layout.addWidget(output_group)

        # === EXPORT SECTION ===
        export_group = QGroupBox("3. Export")
        export_layout = QVBoxLayout()

        self.start_btn = QPushButton("Start Export")
        self.start_btn.setMinimumHeight(38)
        self.start_btn.setEnabled(False)
        self.start_btn.clicked.connect(self.on_start)
        self.start_btn.setStyleSheet("""
            QPushButton:enabled { background-color: #0070d2; color: white; font-weight: bold; }
            QPushButton:disabled { background-color: #ccc; color: #888; }
        """)
        export_layout.addWidget(self.start_btn)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(True)
        self.progress.setFormat("Ready")
        export_layout.addWidget(self.progress)

        export_group.setLayout(export_layout)
        layout.addWidget(export_group)

        # === LOG SECTION ===
        log_layout = QHBoxLayout()
        log_layout.addWidget(QLabel("Log:"))
        log_layout.addStretch()
        clear_btn = QPushButton("Clear")
        clear_btn.setMaximumWidth(60)
        clear_btn.clicked.connect(lambda: self.log.clear())
        log_layout.addWidget(clear_btn)
        layout.addLayout(log_layout)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(120)
        self.log.setStyleSheet("font-family: Consolas, Monaco, monospace; font-size: 11px;")
        layout.addWidget(self.log)

    def _on_custom_domain_toggle(self, checked):
        self.custom_domain_input.setEnabled(checked)
        self.env_combo.setEnabled(not checked)

    def _log(self, msg: str):
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        self.signals.log.emit(f"[{ts}] {msg}")

    @Slot(str)
    def _on_log(self, msg: str):
        self.log.append(msg)
        sb = self.log.verticalScrollBar()
        sb.setValue(sb.maximum())

    @Slot(int, int)
    def _on_progress(self, done: int, total: int):
        if total > 0:
            pct = int(done * 100 / total)
            self.progress.setValue(pct)
            self.progress.setFormat(f"{done}/{total} reports ({pct}%)")

    @Slot(dict)
    def _on_login_success(self, data: dict):
        self.session_info = data
        instance = data.get("instance_url", "")
        api_version = data.get("api_version", "")
        user_name = data.get("user_name", "")
        short_instance = instance.replace("https://", "")
        
        status_text = f"✓ {short_instance}"
        if api_version:
            status_text += f" (API v{api_version})"
        self.status_label.setText(status_text)
        self.status_label.setStyleSheet("color: green; font-weight: bold;")
        
        self._log(f"Login successful: {instance}")
        self._log(f"API Version: v{api_version}")
        if user_name:
            self._log(f"User: {user_name}")
        
        self._update_buttons()
        self._set_inputs_enabled(True)

    @Slot(str)
    def _on_login_error(self, error: str):
        self.status_label.setText("✗ Login failed")
        self.status_label.setStyleSheet("color: red;")
        self._log(f"Login error: {error}")
        self._set_inputs_enabled(True)
        QMessageBox.critical(self, "Login Failed", error)

    @Slot(dict)
    def _on_export_finished(self, result: dict):
        self._export_running = False
        total = result.get("total", 0)
        failed = result.get("failed", [])
        zip_path = result.get("zip", "")

        self.progress.setFormat(f"Done! {total} reports")
        self._log(f"Export completed: {total} reports, {len(failed)} failed")

        if failed:
            self._log("Failed reports:")
            for f in failed[:5]:
                self._log(f"  • {f.get('name')}: {f.get('error')[:50]}")
            if len(failed) > 5:
                self._log(f"  ... and {len(failed) - 5} more")

        self._set_inputs_enabled(True)
        QMessageBox.information(
            self, "Export Complete",
            f"ZIP saved to:\n{zip_path}\n\nTotal: {total} reports\nFailed: {len(failed)}"
        )

    @Slot(str)
    def _on_export_error(self, error: str):
        self._export_running = False
        self.progress.setFormat("Error")
        self._log(f"Export failed: {error}")
        self._set_inputs_enabled(True)
        QMessageBox.critical(self, "Export Failed", error)

    def _set_inputs_enabled(self, enabled: bool):
        self.username_input.setEnabled(enabled)
        self.password_input.setEnabled(enabled)
        self.token_input.setEnabled(enabled)
        self.env_combo.setEnabled(enabled and not self.custom_domain_check.isChecked())
        self.custom_domain_check.setEnabled(enabled)
        self.custom_domain_input.setEnabled(enabled and self.custom_domain_check.isChecked())
        self.login_btn.setEnabled(enabled)
        self.choose_btn.setEnabled(enabled)
        self._update_buttons()

    def _update_buttons(self):
        can_export = (
            self.session_info is not None
            and self.output_zip is not None
            and not self._export_running
        )
        self.start_btn.setEnabled(can_export)

    @Slot()
    def on_login(self):
        username = self.username_input.text().strip()
        password = self.password_input.text()
        token = self.token_input.text()

        if not username:
            QMessageBox.warning(self, "Input Required", "Please enter your username.")
            self.username_input.setFocus()
            return
        if not password:
            QMessageBox.warning(self, "Input Required", "Please enter your password.")
            self.password_input.setFocus()
            return

        self._set_inputs_enabled(False)
        self.status_label.setText("Connecting...")
        self.status_label.setStyleSheet("color: #666;")
        self._log("Authenticating...")

        # Determine domain
        if self.custom_domain_check.isChecked():
            domain = self.custom_domain_input.text().strip()
            if not domain:
                QMessageBox.warning(self, "Input Required", "Please enter custom domain.")
                self._set_inputs_enabled(True)
                return
        else:
            domain = self.env_combo.currentData()

        thread = threading.Thread(
            target=self._login_worker,
            args=(username, password, token, domain),
            daemon=True
        )
        thread.start()

    def _login_worker(self, username, password, token, domain):
        try:
            auth = SalesforceAuth()
            result = auth.login(username, password, token, domain)
            self.signals.login_success.emit(result)
        except Exception as e:
            self.signals.login_error.emit(str(e))

    @Slot()
    def choose_path(self):
        default = f"salesforce_reports_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.zip"
        path, _ = QFileDialog.getSaveFileName(
            self, "Save ZIP File", default, "ZIP files (*.zip)"
        )
        if path:
            if not path.lower().endswith('.zip'):
                path += '.zip'
            self.output_zip = path
            # Show shortened path
            display = path if len(path) < 50 else "..." + path[-47:]
            self.path_label.setText(display)
            self.path_label.setStyleSheet("color: green;")
            self.path_label.setToolTip(path)
            self._log(f"Output: {path}")
            self._update_buttons()

    @Slot()
    def on_start(self):
        if not self.session_info:
            QMessageBox.warning(self, "Not Logged In", "Please login first.")
            return
        if not self.output_zip:
            QMessageBox.warning(self, "No Output", "Please select output location.")
            return

        self._export_running = True
        self._set_inputs_enabled(False)
        self.progress.setValue(0)
        self.progress.setFormat("Starting...")
        self._log("Starting export...")

        thread = threading.Thread(target=self._export_worker, daemon=True)
        thread.start()

    def _export_worker(self):
        try:
            session_id = self.session_info.get("session_id")
            instance_url = self.session_info.get("instance_url")

            def progress_cb(done, total):
                self.signals.progress.emit(done, total)

            exporter = SalesforceReportExporter(
                session_id, instance_url, progress_callback=progress_cb
            )
            result = exporter.export_all_reports_to_zip(self.output_zip)
            self.signals.finished.emit(result)
        except Exception as e:
            self.signals.error.emit(str(e))

    def closeEvent(self, event):
        if self._export_running:
            reply = QMessageBox.question(
                self, "Export Running",
                "Export is in progress. Quit anyway?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply == QMessageBox.No:
                event.ignore()
                return
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())