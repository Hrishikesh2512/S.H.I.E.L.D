"""
ui/project_dialog.py — Project Settings dialog (edits .shield_config.json)
"""

import os
import json
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTextEdit, QFileDialog, QWidget, QTabWidget,
    QCheckBox, QSpinBox, QFormLayout, QMessageBox,
)
from PyQt5.QtGui import QFont
from PyQt5.QtCore import Qt
from core.project import ProjectConfig


_STYLE = """
QDialog {
    background-color: rgba(0,12,22,240);
}
QLabel {
    color: #00ffaa; font-family: Consolas; font-size: 10pt;
}
QLineEdit, QTextEdit, QSpinBox {
    background: rgba(0,20,30,200); color: #00ffcc;
    border: 1px solid rgba(0,255,170,50); border-radius:4px; padding: 4px 8px;
    font-family: Consolas; font-size: 10pt;
}
QTabWidget::pane { border: 1px solid rgba(0,255,170,40); background: rgba(0,12,22,240); }
QTabBar::tab {
    background: rgba(0,60,50,100); color:#00ffaa;
    border:1px solid rgba(0,255,170,40); padding:4px 14px; font-family:Consolas;
}
QTabBar::tab:selected { background: rgba(0,200,150,100); color:black; }
QCheckBox { color:#00ffaa; font-family:Consolas; }
"""

def _btn(text, fn, color="#00ffaa"):
    b = QPushButton(text)
    b.setStyleSheet(f"""
        QPushButton {{
            background: rgba(0,80,60,120); color:{color};
            border:1px solid rgba(0,255,170,50); border-radius:5px; padding:6px 16px;
            font-family:Consolas; font-size:10pt;
        }}
        QPushButton:hover {{ background: rgba(0,200,150,120); color:black; }}
    """)
    b.clicked.connect(fn)
    return b


class ProjectSettingsDialog(QDialog):
    def __init__(self, config: ProjectConfig, parent=None):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("Project Settings")
        self.setMinimumWidth(560)
        self.setStyleSheet(_STYLE)
        self._build_ui()
        self._load_values()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        title = QLabel(f"⚙  Project: {self.config.get('name', '')}")
        title.setFont(QFont("Consolas", 13))
        title.setStyleSheet("color:#00ffff; font-weight:bold;")
        layout.addWidget(title)

        tabs = QTabWidget()
        layout.addWidget(tabs)

        # ── General Tab ──
        gen = QWidget()
        form = QFormLayout(gen)
        form.setSpacing(10)

        self.name_input   = QLineEdit()
        self.python_input = QLineEdit()
        self.entry_input  = QLineEdit()
        self.args_input   = QLineEdit()
        self.font_spin    = QSpinBox(); self.font_spin.setRange(8, 32)
        self.wrap_cb      = QCheckBox("Word wrap")
        self.tab_spin     = QSpinBox(); self.tab_spin.setRange(2, 8)

        browse_py = _btn("Browse…", self._browse_python)
        browse_ep = _btn("Browse…", self._browse_entry)

        py_row = QHBoxLayout()
        py_row.addWidget(self.python_input)
        py_row.addWidget(browse_py)

        ep_row = QHBoxLayout()
        ep_row.addWidget(self.entry_input)
        ep_row.addWidget(browse_ep)

        form.addRow("Project name:",    self.name_input)
        form.addRow("Python path:",     py_row)
        form.addRow("Entry point:",     ep_row)
        form.addRow("Run args:",        self.args_input)
        form.addRow("Font size:",       self.font_spin)
        form.addRow("Tab size:",        self.tab_spin)
        form.addRow("",                 self.wrap_cb)
        tabs.addTab(gen, "General")

        # ── Environment Tab ──
        env_widget = QWidget()
        env_layout = QVBoxLayout(env_widget)
        env_layout.addWidget(QLabel("Environment variables (JSON object):"))
        self.env_input = QTextEdit()
        self.env_input.setPlaceholderText('{\n  "MY_VAR": "value"\n}')
        self.env_input.setFont(QFont("Consolas", 10))
        env_layout.addWidget(self.env_input)
        tabs.addTab(env_widget, "Environment")

        # ── Exclude Tab ──
        excl_widget = QWidget()
        excl_layout = QVBoxLayout(excl_widget)
        excl_layout.addWidget(QLabel("Excluded directories (one per line):"))
        self.excl_input = QTextEdit()
        self.excl_input.setFont(QFont("Consolas", 10))
        excl_layout.addWidget(self.excl_input)
        tabs.addTab(excl_widget, "Exclude")

        # ── Buttons ──
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(_btn("Save", self.save, "#00ffaa"))
        btn_row.addWidget(_btn("Cancel", self.reject, "#ff5555"))
        layout.addLayout(btn_row)

    def _load_values(self):
        c = self.config
        self.name_input.setText(c.get("name", ""))
        self.python_input.setText(c.get("python_path", ""))
        self.entry_input.setText(c.get("entry_point", ""))
        self.args_input.setText(" ".join(c.get("run_args", [])))
        self.font_spin.setValue(c.get("font_size", 12))
        self.tab_spin.setValue(c.get("tab_size", 4))
        self.wrap_cb.setChecked(c.get("word_wrap", False))
        self.env_input.setPlainText(json.dumps(c.get("env", {}), indent=2))
        self.excl_input.setPlainText("\n".join(c.get("exclude_dirs", [])))

    def save(self):
        c = self.config
        c.set("name",        self.name_input.text().strip())
        c.set("python_path", self.python_input.text().strip())
        c.set("entry_point", self.entry_input.text().strip())
        c.set("run_args",    [a for a in self.args_input.text().split() if a])
        c.set("font_size",   self.font_spin.value())
        c.set("tab_size",    self.tab_spin.value())
        c.set("word_wrap",   self.wrap_cb.isChecked())
        c.set("exclude_dirs", [l.strip() for l in self.excl_input.toPlainText().splitlines() if l.strip()])

        try:
            env = json.loads(self.env_input.toPlainText() or "{}")
            c.set("env", env)
        except json.JSONDecodeError as e:
            QMessageBox.warning(self, "Bad JSON", f"Environment JSON is invalid:\n{e}")
            return

        if c.save():
            self.accept()
        else:
            QMessageBox.critical(self, "Error", "Could not save .shield_config.json")

    def _browse_python(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Python Interpreter")
        if path:
            self.python_input.setText(path)

    def _browse_entry(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Entry Point", self.config.folder,
                                               "Python Files (*.py);;All Files (*)")
        if path:
            self.entry_input.setText(os.path.relpath(path, self.config.folder))
