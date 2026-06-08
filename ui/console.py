"""
ui/console.py — Output console with ANSI color stripping, stdin support, and scroll lock
"""

import re
import sys
import subprocess
import threading
import os

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QLineEdit, QPushButton, QLabel,
)
from PyQt5.QtGui import QFont, QColor, QTextCursor
from PyQt5.QtCore import Qt, pyqtSignal, QObject


# ──────────────────────────────────────────────
# Thread-safe output emitter
# ──────────────────────────────────────────────
class _Emitter(QObject):
    stdout_ready = pyqtSignal(str)
    stderr_ready = pyqtSignal(str)
    done         = pyqtSignal(int)  # exit code


# ──────────────────────────────────────────────
# ANSI → HTML color map (basic 16 colors)
# ──────────────────────────────────────────────
_ANSI_COLORS = {
    "30": "#333", "31": "#ff5555", "32": "#55ff55",
    "33": "#ffff55", "34": "#5555ff", "35": "#ff55ff",
    "36": "#55ffff", "37": "#ffffff",
    "90": "#888", "91": "#ff8888", "92": "#88ff88",
    "93": "#ffff88", "94": "#8888ff", "95": "#ff88ff",
    "96": "#88ffff", "97": "#ffffff",
}
_ANSI_RE = re.compile(r'\x1b\[([0-9;]*)m')


def ansi_to_html(text: str) -> str:
    """Convert ANSI escape codes to inline HTML spans."""
    result = []
    last = 0
    open_span = False
    for m in _ANSI_RE.finditer(text):
        result.append(_esc(text[last:m.start()]))
        codes = m.group(1).split(";")
        if open_span:
            result.append("</span>")
            open_span = False
        if codes == ["0"] or codes == [""]:
            pass  # reset
        else:
            color = None
            style_parts = []
            for code in codes:
                if code in _ANSI_COLORS:
                    color = _ANSI_COLORS[code]
                elif code == "1":
                    style_parts.append("font-weight:bold")
                elif code == "3":
                    style_parts.append("font-style:italic")
                elif code == "4":
                    style_parts.append("text-decoration:underline")
            if color:
                style_parts.append(f"color:{color}")
            if style_parts:
                result.append(f'<span style="{";".join(style_parts)}">')
                open_span = True
        last = m.end()
    result.append(_esc(text[last:]))
    if open_span:
        result.append("</span>")
    return "".join(result)


def _esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# ──────────────────────────────────────────────
# Console Widget
# ──────────────────────────────────────────────
class ConsoleWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._process: subprocess.Popen = None
        self._lock = threading.Lock()
        self._scroll_locked = False

        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        # Top bar
        top = QHBoxLayout()
        self._title = QLabel("Console")
        self._title.setStyleSheet("color:#00ffaa; font-family:Consolas; font-size:10pt;")
        top.addWidget(self._title)
        top.addStretch()

        def _btn(text, tip, fn):
            b = QPushButton(text)
            b.setToolTip(tip)
            b.setFixedHeight(22)
            b.setStyleSheet("""
                QPushButton {
                    background:rgba(0,60,50,100); color:#00ffcc;
                    border:1px solid rgba(0,255,200,40); border-radius:4px;
                    padding:0 6px; font-family:Consolas; font-size:9pt;
                }
                QPushButton:hover { background:rgba(0,180,130,120); color:black; }
            """)
            b.clicked.connect(fn)
            return b

        top.addWidget(_btn("🔒", "Toggle scroll lock", self.toggle_scroll_lock))
        top.addWidget(_btn("🛑", "Kill process",        self.kill_process))
        top.addWidget(_btn("🧹", "Clear",               self.clear))
        layout.addLayout(top)

        # Output area
        self.output = QTextEdit()
        self.output.setReadOnly(True)
        self.output.setFont(QFont("Consolas", 11))
        self.output.setStyleSheet("""
            QTextEdit {
                background-color: rgba(0,15,25,210);
                color: #aaffcc;
                border: 1px solid rgba(0,255,170,60);
                border-radius: 6px;
                padding: 6px;
                selection-background-color: rgba(0,200,150,80);
            }
        """)
        layout.addWidget(self.output)

        # stdin bar
        stdin_row = QHBoxLayout()
        self._stdin = QLineEdit()
        self._stdin.setPlaceholderText("stdin input (press Enter to send)…")
        self._stdin.setFont(QFont("Consolas", 11))
        self._stdin.setStyleSheet("""
            QLineEdit {
                background: rgba(0,20,30,200); color:#00ffcc;
                border: 1px solid rgba(0,255,170,50); border-radius:4px; padding:4px 8px;
            }
        """)
        self._stdin.returnPressed.connect(self._send_stdin)
        stdin_row.addWidget(self._stdin)
        layout.addLayout(stdin_row)

    # ── Public API ──────────────────────────────
    def run(self, cmd: list, env: dict = None, cwd: str = None):
        """Run a command and stream output."""
        self.kill_process()
        self.append_html(
            f"<b style='color:#00ffff'>▶ {' '.join(cmd)}</b><br>"
        )
        em = _Emitter()
        em.stdout_ready.connect(self._on_stdout)
        em.stderr_ready.connect(self._on_stderr)
        em.done.connect(self._on_done)

        def _runner():
            try:
                self._process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    stdin=subprocess.PIPE,
                    text=True,
                    env=env or dict(os.environ),
                    cwd=cwd,
                )
                # Stream stdout
                for line in iter(self._process.stdout.readline, ""):
                    em.stdout_ready.emit(line)
                # Stream stderr
                for line in iter(self._process.stderr.readline, ""):
                    em.stderr_ready.emit(line)
                self._process.wait()
                em.done.emit(self._process.returncode)
            except Exception as e:
                em.stderr_ready.emit(f"[S.H.I.E.L.D. Error] {e}\n")
                em.done.emit(-1)

        threading.Thread(target=_runner, daemon=True).start()

    def run_code_string(self, code: str, python_path: str, env: dict = None):
        """Run a Python code string directly via -c."""
        self.kill_process()
        self.append_html("<b style='color:#00ffff'>▶ Running buffer...</b><br>")
        em = _Emitter()
        em.stdout_ready.connect(self._on_stdout)
        em.stderr_ready.connect(self._on_stderr)
        em.done.connect(self._on_done)

        def _runner():
            try:
                self._process = subprocess.Popen(
                    [python_path, "-u", "-c", code],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    stdin=subprocess.PIPE,
                    text=True,
                    env=env or dict(os.environ),
                )
                for line in iter(self._process.stdout.readline, ""):
                    em.stdout_ready.emit(line)
                for line in iter(self._process.stderr.readline, ""):
                    em.stderr_ready.emit(line)
                self._process.wait()
                em.done.emit(self._process.returncode)
            except Exception as e:
                em.stderr_ready.emit(f"[Error] {e}\n")
                em.done.emit(-1)

        threading.Thread(target=_runner, daemon=True).start()

    def clear(self):
        self.output.clear()

    def kill_process(self):
        if self._process and self._process.poll() is None:
            try:
                self._process.terminate()
                self.append_html("<b style='color:#ffaa00'>⚠ Process terminated.</b><br>")
            except Exception:
                pass
        self._process = None

    def toggle_scroll_lock(self):
        self._scroll_locked = not self._scroll_locked
        self._title.setText("Console 🔒" if self._scroll_locked else "Console")

    def append_html(self, html: str):
        self.output.moveCursor(QTextCursor.End)
        self.output.insertHtml(html)
        if not self._scroll_locked:
            self.output.ensureCursorVisible()

    def append_plain(self, text: str, color: str = "#aaffcc"):
        html = f"<pre style='color:{color}; margin:0; white-space:pre-wrap;'>{ansi_to_html(text)}</pre>"
        self.append_html(html)

    # ── Slots ────────────────────────────────────
    def _on_stdout(self, line: str):
        self.append_plain(line.rstrip("\n"), "#aaffcc")

    def _on_stderr(self, line: str):
        self.append_plain(line.rstrip("\n"), "#ff9999")

    def _on_done(self, code: int):
        color = "#00ffaa" if code == 0 else "#ff5555"
        self.append_html(
            f"<br><b style='color:{color}'>─── Exited with code {code} ───</b><br>"
        )
        self._process = None

    def _send_stdin(self):
        text = self._stdin.text().strip()
        if self._process and self._process.poll() is None:
            try:
                self._process.stdin.write(text + "\n")
                self._process.stdin.flush()
                self.append_html(f"<b style='color:#ffdd88'>← {_esc(text)}</b><br>")
            except Exception:
                pass
        self._stdin.clear()
