"""
ui/ai_panel.py — AI Assistant panel (Claude API via Anthropic)

Drop this panel into any tab. It sends the current editor code + user question to Claude
and streams the response back into the panel's output area.

Requires:  pip install anthropic
Falls back gracefully if anthropic is not installed.
"""

import threading
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QLineEdit,
    QPushButton, QLabel, QComboBox,
)
from PyQt5.QtGui import QFont, QColor, QTextCursor
from PyQt5.QtCore import Qt, pyqtSignal, QObject


# ──────────────────────────────────────────────
# Thread-safe response emitter
# ──────────────────────────────────────────────
class _AIEmitter(QObject):
    chunk   = pyqtSignal(str)
    done    = pyqtSignal()
    error   = pyqtSignal(str)


# ──────────────────────────────────────────────
# Panel
# ──────────────────────────────────────────────
class AIPanel(QWidget):
    """
    Embeddable AI assistant panel.
    Call set_code_getter(fn) to supply a callable that returns the current editor text.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._code_getter = lambda: ""
        self._history = []   # list of {"role": ..., "content": ...}
        self._streaming = False
        self._build_ui()

    def set_code_getter(self, fn):
        """Pass a callable() → str that returns the active editor's text."""
        self._code_getter = fn

    # ── UI ──────────────────────────────────────
    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        # Header
        hdr = QHBoxLayout()
        title = QLabel("🤖 AI Assistant")
        title.setFont(QFont("Consolas", 11))
        title.setStyleSheet("color:#00ffff; font-weight:bold;")
        hdr.addWidget(title)
        hdr.addStretch()

        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Explain", "Debug", "Refactor", "Docs", "Chat"])
        self.mode_combo.setStyleSheet("""
            QComboBox {
                background: rgba(0,20,30,200); color:#00ffcc;
                border:1px solid rgba(0,255,170,50); border-radius:4px;
                padding:2px 8px; font-family:Consolas; font-size:10pt;
            }
            QComboBox QAbstractItemView {
                background: rgba(0,20,30,230); color:#00ffcc;
                selection-background-color: rgba(0,200,150,120);
            }
        """)
        hdr.addWidget(self.mode_combo)

        clear_btn = self._btn("Clear", self._clear_chat)
        hdr.addWidget(clear_btn)
        layout.addLayout(hdr)

        # Chat output
        self.chat_output = QTextEdit()
        self.chat_output.setReadOnly(True)
        self.chat_output.setFont(QFont("Consolas", 10))
        self.chat_output.setStyleSheet("""
            QTextEdit {
                background: rgba(0,12,22,220);
                color: #ccffee;
                border: 1px solid rgba(0,255,170,50);
                border-radius: 6px;
                padding: 6px;
            }
        """)
        layout.addWidget(self.chat_output)

        # Input row
        input_row = QHBoxLayout()
        self.user_input = QLineEdit()
        self.user_input.setPlaceholderText("Ask about your code…")
        self.user_input.setFont(QFont("Consolas", 10))
        self.user_input.setStyleSheet("""
            QLineEdit {
                background: rgba(0,20,30,200); color:#00ffcc;
                border:1px solid rgba(0,255,170,50); border-radius:4px; padding:4px 8px;
            }
        """)
        self.user_input.returnPressed.connect(self._send)
        input_row.addWidget(self.user_input)

        send_btn = self._btn("Send ↵", self._send, accent="#00ffaa")
        input_row.addWidget(send_btn)
        layout.addLayout(input_row)

        self.context_cb_label = QLabel("Include editor code in context")
        self.context_cb_label.setStyleSheet("color:#00ffaa; font-family:Consolas; font-size:9pt;")
        layout.addWidget(self.context_cb_label)

    def _btn(self, text, fn, accent="#00ffcc"):
        b = QPushButton(text)
        b.setStyleSheet(f"""
            QPushButton {{
                background: rgba(0,60,50,120); color:{accent};
                border:1px solid rgba(0,255,170,50); border-radius:4px; padding:4px 12px;
                font-family:Consolas; font-size:10pt;
            }}
            QPushButton:hover {{ background:rgba(0,180,130,120); color:black; }}
        """)
        b.clicked.connect(fn)
        return b

    # ── Logic ────────────────────────────────────
    def _clear_chat(self):
        self.chat_output.clear()
        self._history.clear()

    def _send(self):
        if self._streaming:
            return

        user_text = self.user_input.text().strip()
        if not user_text:
            return
        self.user_input.clear()

        code = self._code_getter()
        mode = self.mode_combo.currentText()
        system_prompt = self._system_for_mode(mode, code)

        self._append_chat("You", user_text, "#ffdd88")
        self._history.append({"role": "user", "content": user_text})

        em = _AIEmitter()
        em.chunk.connect(self._on_chunk)
        em.done.connect(self._on_done)
        em.error.connect(self._on_error)

        self._streaming = True
        self._append_chat("Assistant", "", "#00ffcc")  # placeholder heading

        threading.Thread(
            target=self._call_api,
            args=(system_prompt, list(self._history), em),
            daemon=True,
        ).start()

    def _call_api(self, system: str, messages: list, em: _AIEmitter):
        try:
            import anthropic
            client = anthropic.Anthropic()
            with client.messages.stream(
                model="claude-sonnet-4-20250514",
                max_tokens=2048,
                system=system,
                messages=messages,
            ) as stream:
                full = ""
                for text in stream.text_stream:
                    full += text
                    em.chunk.emit(text)
                self._history.append({"role": "assistant", "content": full})
            em.done.emit()
        except ImportError:
            em.error.emit(
                "anthropic package not installed.\nRun: pip install anthropic"
            )
        except Exception as e:
            em.error.emit(str(e))

    def _system_for_mode(self, mode: str, code: str) -> str:
        base = "You are an expert software engineer assistant inside S.H.I.E.L.D. IDE."
        code_block = f"\n\nCurrent editor code:\n```\n{code}\n```" if code.strip() else ""
        prompts = {
            "Explain":  f"{base} Explain the provided code clearly and concisely.{code_block}",
            "Debug":    f"{base} Identify bugs and issues in the provided code. Be specific.{code_block}",
            "Refactor": f"{base} Suggest concrete refactoring improvements.{code_block}",
            "Docs":     f"{base} Write docstrings and inline comments for the provided code.{code_block}",
            "Chat":     f"{base} Answer general programming questions helpfully.{code_block}",
        }
        return prompts.get(mode, base + code_block)

    def _append_chat(self, role: str, text: str, color: str):
        self.chat_output.moveCursor(QTextCursor.End)
        if text:
            self.chat_output.insertHtml(
                f"<b style='color:{color}'>{role}:</b> "
                f"<span style='color:#ccffee'>{text}</span><br>"
            )
        else:
            self.chat_output.insertHtml(f"<b style='color:{color}'>{role}:</b> ")
        self.chat_output.ensureCursorVisible()

    def _on_chunk(self, text: str):
        # Append to last line (streaming in-place)
        cursor = self.chat_output.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertText(text)
        self.chat_output.setTextCursor(cursor)
        self.chat_output.ensureCursorVisible()

    def _on_done(self):
        self._streaming = False
        self.chat_output.moveCursor(QTextCursor.End)
        self.chat_output.insertHtml("<br>")

    def _on_error(self, msg: str):
        self._streaming = False
        self.chat_output.moveCursor(QTextCursor.End)
        self.chat_output.insertHtml(
            f"<br><b style='color:#ff5555'>Error: {msg}</b><br>"
        )
