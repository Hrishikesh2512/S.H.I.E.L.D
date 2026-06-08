"""
ui/statusbar.py — Status bar: git branch, CPU/RAM, cursor pos, language, encoding
"""

import os
import datetime
import subprocess
import threading

import psutil
from PyQt5.QtWidgets import QWidget, QHBoxLayout, QLabel, QFrame
from PyQt5.QtGui import QFont, QColor
from PyQt5.QtCore import QTimer, Qt


def _label(text="", color="#00ffaa", bold=False):
    lbl = QLabel(text)
    weight = "bold" if bold else "normal"
    lbl.setStyleSheet(
        f"color:{color}; font-family:Consolas; font-size:10pt; font-weight:{weight};"
    )
    return lbl


def _sep():
    sep = QLabel("│")
    sep.setStyleSheet("color:rgba(0,255,170,40); font-family:Consolas; font-size:10pt;")
    return sep


class StatusBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(28)
        self.setStyleSheet("""
            QWidget {
                background-color: rgba(0,10,18,200);
                border-top: 1px solid rgba(0,255,170,40);
                border-radius: 0px;
            }
        """)

        self._git_branch = ""
        self._git_dirty  = False
        self._folder     = None

        self._build_ui()
        self._start_timers()

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 10, 0)
        layout.setSpacing(8)

        self.git_lbl      = _label("", "#aaddff")
        self.workspace_lbl= _label("(no workspace)", "#00ffaa")
        self.lang_lbl     = _label("Python", "#ffaa00")
        self.cursor_lbl   = _label("Ln 1, Col 1", "#aaffcc")
        self.cpu_lbl      = _label("CPU 0%",  "#00ffcc")
        self.ram_lbl      = _label("RAM 0%",  "#00ffcc")
        self.time_lbl     = _label("00:00:00", "#aaaaaa")
        self.msg_lbl      = _label("", "#ffdd88")

        for w in [
            self.git_lbl, _sep(),
            self.workspace_lbl, _sep(),
            self.lang_lbl, _sep(),
            self.cursor_lbl, _sep(),
        ]:
            layout.addWidget(w)

        layout.addStretch()
        layout.addWidget(self.msg_lbl)
        layout.addWidget(_sep())
        layout.addWidget(self.cpu_lbl)
        layout.addWidget(_sep())
        layout.addWidget(self.ram_lbl)
        layout.addWidget(_sep())
        layout.addWidget(self.time_lbl)

    def _start_timers(self):
        self._sys_timer = QTimer()
        self._sys_timer.timeout.connect(self._update_sys)
        self._sys_timer.start(1500)

        self._git_timer = QTimer()
        self._git_timer.timeout.connect(self._poll_git)
        self._git_timer.start(5000)

    # ── Public setters ────────────────────────────
    def set_workspace(self, folder: str):
        self._folder = folder
        name = os.path.basename(folder) if folder else "(no workspace)"
        self.workspace_lbl.setText(f"📁 {name}")
        self._poll_git()

    def set_language(self, lang: str):
        icons = {
            "python": "🐍", "javascript": "⚡", "bash": "🐚",
            "c": "⚙", "json": "{}", "markdown": "📝",
        }
        icon = icons.get(lang, "")
        self.lang_lbl.setText(f"{icon} {lang.capitalize()}")

    def set_cursor(self, line: int, col: int):
        self.cursor_lbl.setText(f"Ln {line}, Col {col}")

    def show_message(self, msg: str, color: str = "#ffdd88", duration_ms: int = 3000):
        self.msg_lbl.setText(msg)
        self.msg_lbl.setStyleSheet(
            f"color:{color}; font-family:Consolas; font-size:10pt;"
        )
        QTimer.singleShot(duration_ms, lambda: self.msg_lbl.setText(""))

    # ── Git polling (background thread) ──────────
    def _poll_git(self):
        if not self._folder:
            self.git_lbl.setText("")
            return
        threading.Thread(target=self._fetch_git, daemon=True).start()

    def _fetch_git(self):
        folder = self._folder
        try:
            branch = subprocess.check_output(
                ["git", "-C", folder, "rev-parse", "--abbrev-ref", "HEAD"],
                stderr=subprocess.DEVNULL, timeout=2
            ).decode().strip()

            status = subprocess.check_output(
                ["git", "-C", folder, "status", "--porcelain"],
                stderr=subprocess.DEVNULL, timeout=2
            ).decode().strip()
            dirty = bool(status)

            self._git_branch = branch
            self._git_dirty  = dirty
            self._update_git_label()
        except Exception:
            self._git_branch = ""
            self._update_git_label()

    def _update_git_label(self):
        if not self._git_branch:
            self.git_lbl.setText("")
            return
        dirty_marker = " ●" if self._git_dirty else ""
        color = "#ffaa55" if self._git_dirty else "#aaddff"
        self.git_lbl.setText(f"⎇ {self._git_branch}{dirty_marker}")
        self.git_lbl.setStyleSheet(
            f"color:{color}; font-family:Consolas; font-size:10pt;"
        )

    # ── System stats ─────────────────────────────
    def _update_sys(self):
        cpu = psutil.cpu_percent()
        ram = psutil.virtual_memory().percent
        now = datetime.datetime.now().strftime("%H:%M:%S")

        cpu_color = "#ff5555" if cpu > 80 else "#ffaa00" if cpu > 50 else "#00ffcc"
        ram_color = "#ff5555" if ram > 85 else "#ffaa00" if ram > 60 else "#00ffcc"

        self.cpu_lbl.setText(f"CPU {cpu:.0f}%")
        self.cpu_lbl.setStyleSheet(
            f"color:{cpu_color}; font-family:Consolas; font-size:10pt;"
        )
        self.ram_lbl.setText(f"RAM {ram:.0f}%")
        self.ram_lbl.setStyleSheet(
            f"color:{ram_color}; font-family:Consolas; font-size:10pt;"
        )
        self.time_lbl.setText(now)
