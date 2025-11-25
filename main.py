# main.py - UPDATED WITH DUAL MODE EXPORT
import os
import sys
import threading
import datetime
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QFileDialog, QLabel, QProgressBar, QTextEdit, QMessageBox,
    QLineEdit, QComboBox, QGroupBox, QFormLayout, QCheckBox,
    QTabWidget, QScrollArea, QFrame
)
from PySide6.QtCore import Signal, Slot, QObject, Qt
from PySide6.QtGui import QFont
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
    folders_loaded = Signal(list)
    folders_error = Signal(str)
    reports_loaded = Signal(list)  # NEW: For loading all reports
    reports_error = Signal(str)    # NEW: For report loading errors


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Salesforce Reports Exporter")
        self.resize(700, 750)
        self.signals = WorkerSignals()
        self._connect_signals()
        self._setup_ui()
        self.session_info = None
        self.output_zip = None
        self._export_running = False
        self.available_folders = []
        self.available_reports = []  # NEW: Store all reports
        self.selected_reports = set()  # NEW: Store selected report IDs
        self.selected_folder_name = "All_Reports"

    def _connect_signals(self):
        self.signals.progress.connect(self._on_progress)
        self.signals.log.connect(self._on_log)
        self.signals.finished.connect(self._on_export_finished)
        self.signals.error.connect(self._on_export_error)
        self.signals.login_success.connect(self._on_login_success)
        self.signals.login_error.connect(self._on_login_error)
        self.signals.folders_loaded.connect(self._on_folders_loaded)
        self.signals.folders_error.connect(self._on_folders_error)
        self.signals.reports_loaded.connect(self._on_reports_loaded)  # NEW
        self.signals.reports_error.connect(self._on_reports_error)    # NEW

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # Header
        header = QLabel("Salesforce Report Exporter")
        header.setStyleSheet("font-size: 16px; font-weight: bold; padding: 5px;")
        layout.addWidget(header)

        subtitle = QLabel("Export reports by folder or select specific reports. Works on any org!")
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

        # === EXPORT MODE TABS ===
        self.export_tabs = QTabWidget()
        self.export_tabs.setEnabled(False)  # Disabled until login
        
        # Tab 1: Export by Folder
        self.folder_tab = self._create_folder_tab()
        self.export_tabs.addTab(self.folder_tab, "📁 Export by Folder")
        
        # Tab 2: Export Selected Reports
        self.selected_tab = self._create_selected_reports_tab()
        self.export_tabs.addTab(self.selected_tab, "☑️ Export Selected Reports")
        
        layout.addWidget(self.export_tabs)

        # === OUTPUT SECTION (Shared) ===
        output_group = QGroupBox("3. Output Location")
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

        # === EXPORT SECTION (Shared) ===
        export_group = QGroupBox("4. Export")
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

    def _create_folder_tab(self):
        """Create the folder-based export tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        folder_group = QGroupBox("Select Report Folder")
        folder_layout = QVBoxLayout()
        
        # Search box
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Search:"))
        self.folder_search = QLineEdit()
        self.folder_search.setPlaceholderText("Type to filter folders...")
        self.folder_search.textChanged.connect(self._on_search_changed)
        self.folder_search.setEnabled(False)
        search_layout.addWidget(self.folder_search, 1)
        folder_layout.addLayout(search_layout)
        
        # Folder dropdown with refresh button
        folder_combo_layout = QHBoxLayout()
        self.folder_combo = QComboBox()
        self.folder_combo.addItem("Please login first", None)
        self.folder_combo.setEnabled(False)
        self.folder_combo.setMaxVisibleItems(10)
        self.folder_combo.currentIndexChanged.connect(self._on_folder_changed)
        folder_combo_layout.addWidget(self.folder_combo, 1)
        
        self.refresh_folders_btn = QPushButton("Refresh")
        self.refresh_folders_btn.setEnabled(False)
        self.refresh_folders_btn.clicked.connect(self.on_refresh_folders)
        folder_combo_layout.addWidget(self.refresh_folders_btn)
        
        folder_layout.addLayout(folder_combo_layout)
        
        self.folder_info_label = QLabel("Please login to see available folders")
        self.folder_info_label.setStyleSheet("color: #888; font-size: 11px;")
        self.folder_info_label.setWordWrap(True)
        folder_layout.addWidget(self.folder_info_label)
        
        folder_group.setLayout(folder_layout)
        layout.addWidget(folder_group)
        layout.addStretch()
        
        return tab

    def _create_selected_reports_tab(self):
        """Create the selected reports export tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Top controls
        controls_layout = QHBoxLayout()
        
        # Search box
        self.report_search = QLineEdit()
        self.report_search.setPlaceholderText("🔍 Search reports...")
        self.report_search.textChanged.connect(self._on_report_search_changed)
        self.report_search.setEnabled(False)
        controls_layout.addWidget(self.report_search, 1)
        
        # Refresh button
        self.refresh_reports_btn = QPushButton("🔄 Refresh")
        self.refresh_reports_btn.setEnabled(False)
        self.refresh_reports_btn.clicked.connect(self.on_refresh_reports)
        controls_layout.addWidget(self.refresh_reports_btn)
        
        # Select/Deselect All buttons
        self.select_all_btn = QPushButton("✓ Select All")
        self.select_all_btn.setEnabled(False)
        self.select_all_btn.clicked.connect(self.on_select_all_reports)
        controls_layout.addWidget(self.select_all_btn)
        
        self.deselect_all_btn = QPushButton("✗ Clear All")
        self.deselect_all_btn.setEnabled(False)
        self.deselect_all_btn.clicked.connect(self.on_deselect_all_reports)
        controls_layout.addWidget(self.deselect_all_btn)
        
        layout.addLayout(controls_layout)
        
        # Selection counter
        self.selection_counter = QLabel("Selected: 0 reports")
        self.selection_counter.setStyleSheet("font-weight: bold; color: #0070d2; padding: 5px;")
        layout.addWidget(self.selection_counter)
        
        # Scrollable report list
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setMinimumHeight(250)
        
        self.reports_container = QWidget()
        self.reports_layout = QVBoxLayout(self.reports_container)
        self.reports_layout.setAlignment(Qt.AlignTop)
        self.reports_layout.setSpacing(2)
        
        # Placeholder
        placeholder = QLabel("Please login to load reports")
        placeholder.setStyleSheet("color: #888; padding: 20px;")
        placeholder.setAlignment(Qt.AlignCenter)
        self.reports_layout.addWidget(placeholder)
        
        scroll_area.setWidget(self.reports_container)
        layout.addWidget(scroll_area)
        
        return tab

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
        
        self._set_inputs_enabled(True)
        self.export_tabs.setEnabled(True)
        
        # Load folders and reports automatically
        self._log("Loading report folders...")
        self.folder_combo.setEnabled(False)
        self.folder_info_label.setText("Loading folders...")
        self.on_refresh_folders()
        
        self._log("Loading all reports...")
        self.on_refresh_reports()

    @Slot(str)
    def _on_login_error(self, error: str):
        self.status_label.setText("✗ Login failed")
        self.status_label.setStyleSheet("color: red;")
        self._log(f"Login error: {error}")
        self._set_inputs_enabled(True)
        QMessageBox.critical(self, "Login Failed", error)

    @Slot(list)
    def _on_folders_loaded(self, folders: list):
        filtered_folders = [
            f for f in folders 
            if f.get("name") and f.get("name") not in ["Automated Process", "System", "Hidden"]
            and not f.get("name").startswith("__")
        ]
        
        self.available_folders = filtered_folders
        self._populate_folder_combo(filtered_folders)
        
        self.folder_search.setEnabled(True)
        self.refresh_folders_btn.setEnabled(True)
        self._update_buttons()
    
    def _populate_folder_combo(self, folders: list, search_term: str = ""):
        self.folder_combo.clear()
        
        if not folders:
            self.folder_combo.addItem("No folders found", None)
            self.folder_info_label.setText("No report folders found in this org")
            self.folder_combo.setEnabled(False)
            return
        
        if search_term:
            folders = [
                f for f in folders 
                if search_term.lower() in f.get("name", "").lower()
            ]
        
        if not folders and search_term:
            self.folder_combo.addItem(f"No folders matching '{search_term}'", None)
            self.folder_combo.setEnabled(False)
            self.folder_info_label.setText(f"No matches for '{search_term}'")
            return
        
        if not search_term:
            self.folder_combo.addItem("📚 All Reports (All Folders)", "ALL")
        
        for folder in folders:
            folder_name = folder.get("name", "Unnamed")
            folder_id = folder.get("id")
            folder_type = folder.get("type", "")
            
            icon = "📂"
            if folder_type == "Public":
                icon = "🌐"
            elif "My" in folder_name:
                icon = "👤"
            
            display_name = f"{icon} {folder_name}"
            self.folder_combo.addItem(display_name, folder_id)
        
        self.folder_combo.setEnabled(True)
        
        if search_term:
            self.folder_info_label.setText(f"Found {len(folders)} folders matching '{search_term}'")
        else:
            self.folder_info_label.setText(f"Found {len(folders)} folders available")
            self._log(f"Loaded {len(folders)} report folders")
    
    @Slot()
    def _on_search_changed(self):
        search_term = self.folder_search.text().strip()
        self._populate_folder_combo(self.available_folders, search_term)

    @Slot(str)
    def _on_folders_error(self, error: str):
        self.folder_combo.clear()
        self.folder_combo.addItem("Error loading folders", None)
        self.folder_info_label.setText(f"Error: {error}")
        self.folder_combo.setEnabled(False)
        self.refresh_folders_btn.setEnabled(True)
        self._log(f"Error loading folders: {error}")

    @Slot()
    def _on_folder_changed(self):
        current_data = self.folder_combo.currentData()
        current_text = self.folder_combo.currentText()
        
        if current_data:
            if current_data == "ALL":
                self.folder_info_label.setText("Will export all reports from all folders")
                self.selected_folder_name = "All_Reports"
            else:
                folder_name = current_text.split(" ", 1)[1] if " " in current_text else current_text
                self.folder_info_label.setText(f"Selected: {folder_name}")
                self.selected_folder_name = folder_name
            
            if self.output_zip:
                self._update_zip_name(self.selected_folder_name)
        
        self._update_buttons()
    
    # NEW: Report selection methods
    @Slot(list)
    def _on_reports_loaded(self, reports: list):
        self.available_reports = reports
        self._populate_reports_list(reports)
        
        self.report_search.setEnabled(True)
        self.refresh_reports_btn.setEnabled(True)
        self.select_all_btn.setEnabled(True)
        self.deselect_all_btn.setEnabled(True)
        
        self._log(f"Loaded {len(reports)} reports")
        self._update_buttons()
    
    @Slot(str)
    def _on_reports_error(self, error: str):
        self._log(f"Error loading reports: {error}")
        QMessageBox.warning(self, "Error", f"Failed to load reports: {error}")
    
    def _populate_reports_list(self, reports: list, search_term: str = ""):
        # Clear existing checkboxes
        while self.reports_layout.count():
            child = self.reports_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        if not reports:
            placeholder = QLabel("No reports found")
            placeholder.setStyleSheet("color: #888; padding: 20px;")
            placeholder.setAlignment(Qt.AlignCenter)
            self.reports_layout.addWidget(placeholder)
            return
        
        # Filter by search term
        filtered_reports = reports
        if search_term:
            filtered_reports = [
                r for r in reports
                if search_term.lower() in r.get("name", "").lower()
            ]
        
        if not filtered_reports:
            placeholder = QLabel(f"No reports matching '{search_term}'")
            placeholder.setStyleSheet("color: #888; padding: 20px;")
            placeholder.setAlignment(Qt.AlignCenter)
            self.reports_layout.addWidget(placeholder)
            return
        
        # Add checkboxes for each report
        for report in filtered_reports:
            report_id = report.get("id")
            report_name = report.get("name", "Unnamed Report")
            folder_name = report.get("folderName", "Unknown Folder")
            
            checkbox = QCheckBox(f"{report_name} ({folder_name})")
            checkbox.setProperty("report_id", report_id)
            checkbox.setProperty("report_name", report_name)
            
            # Restore selection state
            if report_id in self.selected_reports:
                checkbox.setChecked(True)
            
            checkbox.stateChanged.connect(self._on_report_checkbox_changed)
            self.reports_layout.addWidget(checkbox)
        
        self._update_selection_counter()
    
    @Slot()
    def _on_report_checkbox_changed(self):
        sender = self.sender()
        report_id = sender.property("report_id")
        
        if sender.isChecked():
            self.selected_reports.add(report_id)
        else:
            self.selected_reports.discard(report_id)
        
        self._update_selection_counter()
        self._update_buttons()
    
    @Slot()
    def _on_report_search_changed(self):
        search_term = self.report_search.text().strip()
        self._populate_reports_list(self.available_reports, search_term)
    
    @Slot()
    def on_select_all_reports(self):
        # Get currently visible reports (after search filter)
        search_term = self.report_search.text().strip()
        filtered_reports = self.available_reports
        if search_term:
            filtered_reports = [
                r for r in self.available_reports
                if search_term.lower() in r.get("name", "").lower()
            ]
        
        # Add all visible reports to selection
        for report in filtered_reports:
            self.selected_reports.add(report.get("id"))
        
        # Update UI
        self._populate_reports_list(self.available_reports, search_term)
        self._update_buttons()
    
    @Slot()
    def on_deselect_all_reports(self):
        self.selected_reports.clear()
        search_term = self.report_search.text().strip()
        self._populate_reports_list(self.available_reports, search_term)
        self._update_buttons()
    
    def _update_selection_counter(self):
        count = len(self.selected_reports)
        self.selection_counter.setText(f"Selected: {count} report{'s' if count != 1 else ''}")
        
        if count > 0:
            self.selection_counter.setStyleSheet("font-weight: bold; color: #0070d2; padding: 5px;")
        else:
            self.selection_counter.setStyleSheet("font-weight: bold; color: #888; padding: 5px;")
    
    def _update_zip_name(self, folder_name: str):
        if not self.output_zip:
            return
        
        directory = os.path.dirname(self.output_zip)
        
        safe_folder_name = "".join(c if c.isalnum() or c in " ._-" else "_" for c in folder_name)
        safe_folder_name = safe_folder_name.strip("_ ").replace(" ", "_")
        
        if not safe_folder_name:
            safe_folder_name = "reports"
        
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M')
        new_filename = f"salesforce_reports_{safe_folder_name}_{timestamp}.zip"
        
        if directory:
            self.output_zip = os.path.join(directory, new_filename)
        else:
            self.output_zip = new_filename
        
        display = self.output_zip if len(self.output_zip) < 50 else "..." + self.output_zip[-47:]
        self.path_label.setText(display)
        self.path_label.setToolTip(self.output_zip)
        
        self._log(f"Output filename updated: {new_filename}")

    def _set_inputs_enabled(self, enabled: bool):
        self.username_input.setEnabled(enabled)
        self.password_input.setEnabled(enabled)
        self.token_input.setEnabled(enabled)
        self.env_combo.setEnabled(enabled and not self.custom_domain_check.isChecked())
        self.custom_domain_check.setEnabled(enabled)
        self.custom_domain_input.setEnabled(enabled and self.custom_domain_check.isChecked())
        self.login_btn.setEnabled(enabled)
        self.choose_btn.setEnabled(enabled)
        self.folder_search.setEnabled(enabled and self.session_info is not None)
        self._update_buttons()

    def _update_buttons(self):
        current_tab = self.export_tabs.currentIndex()
        
        if current_tab == 0:  # Folder mode
            can_export = (
                self.session_info is not None
                and self.output_zip is not None
                and not self._export_running
                and self.folder_combo.currentData() is not None
            )
        else:  # Selected reports mode
            can_export = (
                self.session_info is not None
                and self.output_zip is not None
                and not self._export_running
                and len(self.selected_reports) > 0
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
    def on_refresh_folders(self):
        if not self.session_info:
            return
        
        self.refresh_folders_btn.setEnabled(False)
        self.folder_combo.setEnabled(False)
        self.folder_info_label.setText("Loading folders...")
        
        thread = threading.Thread(target=self._load_folders_worker, daemon=True)
        thread.start()

    def _load_folders_worker(self):
        try:
            session_id = self.session_info.get("session_id")
            instance_url = self.session_info.get("instance_url")
            
            exporter = SalesforceReportExporter(session_id, instance_url)
            folders = exporter.list_report_folders()
            self.signals.folders_loaded.emit(folders)
        except Exception as e:
            self.signals.folders_error.emit(str(e))
    
    @Slot()
    def on_refresh_reports(self):
        if not self.session_info:
            return
        
        self.refresh_reports_btn.setEnabled(False)
        self.report_search.setEnabled(False)
        self.select_all_btn.setEnabled(False)
        self.deselect_all_btn.setEnabled(False)
        
        # Clear selections on refresh
        self.selected_reports.clear()
        self._update_selection_counter()
        
        thread = threading.Thread(target=self._load_reports_worker, daemon=True)
        thread.start()
    
    def _load_reports_worker(self):
        try:
            session_id = self.session_info.get("session_id")
            instance_url = self.session_info.get("instance_url")
            
            exporter = SalesforceReportExporter(session_id, instance_url)
            reports = exporter.list_reports()  # Get all reports
            self.signals.reports_loaded.emit(reports)
        except Exception as e:
            self.signals.reports_error.emit(str(e))

    @Slot()
    def choose_path(self):
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M')
        safe_folder = "".join(c if c.isalnum() or c in " ._-" else "_" for c in self.selected_folder_name)
        safe_folder = safe_folder.strip("_ ").replace(" ", "_")
        
        if not safe_folder:
            safe_folder = "reports"
        
        default = f"salesforce_reports_{safe_folder}_{timestamp}.zip"
        
        path, _ = QFileDialog.getSaveFileName(
            self, "Save ZIP File", default, "ZIP files (*.zip)"
        )
        if path:
            if not path.lower().endswith('.zip'):
                path += '.zip'
            self.output_zip = path
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
        
        current_tab = self.export_tabs.currentIndex()
        
        if current_tab == 0:  # Folder mode
            selected_folder_id = self.folder_combo.currentData()
            if not selected_folder_id:
                QMessageBox.warning(self, "No Folder Selected", "Please select a folder to export.")
                return
            
            self._export_running = True
            self._set_inputs_enabled(False)
            self.progress.setValue(0)
            self.progress.setFormat("Starting...")
            
            folder_name = self.folder_combo.currentText()
            if selected_folder_id == "ALL":
                self._log("Starting export of ALL reports from ALL folders...")
            else:
                self._log(f"Starting export from folder: {folder_name}")
            
            thread = threading.Thread(
                target=self._export_worker_folder,
                args=(selected_folder_id,),
                daemon=True
            )
            thread.start()
        
        else:  # Selected reports mode
            if len(self.selected_reports) == 0:
                QMessageBox.warning(self, "No Reports Selected", "Please select at least one report.")
                return
            
            self._export_running = True
            self._set_inputs_enabled(False)
            self.progress.setValue(0)
            self.progress.setFormat("Starting...")
            
            self._log(f"Starting export of {len(self.selected_reports)} selected reports...")
            
            thread = threading.Thread(
                target=self._export_worker_selected,
                args=(list(self.selected_reports),),
                daemon=True
            )
            thread.start()

    def _export_worker_folder(self, folder_id):
        try:
            session_id = self.session_info.get("session_id")
            instance_url = self.session_info.get("instance_url")

            def progress_cb(done, total):
                self.signals.progress.emit(done, total)

            exporter = SalesforceReportExporter(
                session_id, instance_url, progress_callback=progress_cb
            )
            
            if folder_id == "ALL":
                result = exporter.export_all_reports_to_zip(self.output_zip)
            else:
                result = exporter.export_reports_by_folder_to_zip(
                    self.output_zip, 
                    folder_id
                )
            
            self.signals.finished.emit(result)
        except Exception as e:
            self.signals.error.emit(str(e))
    
    def _export_worker_selected(self, report_ids):
        try:
            session_id = self.session_info.get("session_id")
            instance_url = self.session_info.get("instance_url")

            def progress_cb(done, total):
                self.signals.progress.emit(done, total)

            exporter = SalesforceReportExporter(
                session_id, instance_url, progress_callback=progress_cb
            )
            
            result = exporter.export_selected_reports_to_zip(
                self.output_zip,
                report_ids
            )
            
            self.signals.finished.emit(result)
        except Exception as e:
            self.signals.error.emit(str(e))

    @Slot(dict)
    def _on_export_finished(self, result: dict):
        self._export_running = False
        total = result.get("total", 0)
        failed = result.get("failed", [])
        zip_path = result.get("zip", "")
        folder_name = result.get("folder_name", "selected reports")

        self.progress.setFormat(f"Done! {total} reports")
        self._log(f"Export completed: {total} reports from {folder_name}, {len(failed)} failed")

        if failed:
            self._log("Failed reports:")
            for f in failed[:5]:
                self._log(f"  • {f.get('name')}: {f.get('error')[:50]}")
            if len(failed) > 5:
                self._log(f"  ... and {len(failed) - 5} more")

        self._set_inputs_enabled(True)
        QMessageBox.information(
            self, "Export Complete",
            f"ZIP saved to:\n{zip_path}\n\nSource: {folder_name}\nTotal: {total} reports\nFailed: {len(failed)}"
        )

    @Slot(str)
    def _on_export_error(self, error: str):
        self._export_running = False
        self.progress.setFormat("Error")
        self._log(f"Export failed: {error}")
        self._set_inputs_enabled(True)
        QMessageBox.critical(self, "Export Failed", error)

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