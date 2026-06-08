"""
core/editor.py — EditorTab with line numbers, find/replace, auto-indent, multi-language
"""

import os
from PyQt5.QtWidgets import (
    QWidget, QHBoxLayout, QTextEdit, QPlainTextEdit,
    QAbstractScrollArea, QSizePolicy, QToolBar, QLabel,
    QLineEdit, QPushButton, QCheckBox, QVBoxLayout, QFrame,
)
from PyQt5.QtGui import (
    QFont, QColor, QTextCursor, QPainter, QTextFormat,
    QTextCharFormat, QPalette,
)
from PyQt5.QtCore import Qt, QRect, QSize, QRegularExpression, pyqtSignal

from core.highlighter import UniversalHighlighter, detect_language


# ──────────────────────────────────────────────
# Line Number Gutter
# ──────────────────────────────────────────────
class LineNumberArea(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor

    def sizeHint(self):
        return QSize(self.editor.line_number_area_width(), 0)

    def paintEvent(self, event):
        self.editor.line_number_area_paint_event(event)


# ──────────────────────────────────────────────
# Code Editor (QPlainTextEdit base for perf)
# ──────────────────────────────────────────────
class CodeEditor(QPlainTextEdit):
    run_requested        = pyqtSignal()
    run_clear_requested  = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.line_number_area = LineNumberArea(self)

        self.blockCountChanged.connect(self.update_line_number_area_width)
        self.updateRequest.connect(self.update_line_number_area)
        self.cursorPositionChanged.connect(self.highlight_current_line)

        self.update_line_number_area_width(0)
        self.highlight_current_line()

        self.setFont(QFont("Consolas", 12))
        self.setTabStopDistance(32)  # 4-space tabs visually
        self.setStyleSheet("""
            QPlainTextEdit {
                background-color: rgba(5,10,20,200);
                color: #00ffcc;
                border: none;
                padding: 4px 4px 4px 0px;
                selection-background-color: rgba(0,200,200,80);
            }
        """)

    # ── Line number width ──
    def line_number_area_width(self):
        digits = max(1, len(str(self.blockCount())))
        return 10 + self.fontMetrics().horizontalAdvance("9") * (digits + 1)

    def update_line_number_area_width(self, _):
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

    def update_line_number_area(self, rect, dy):
        if dy:
            self.line_number_area.scroll(0, dy)
        else:
            self.line_number_area.update(0, rect.y(), self.line_number_area.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self.update_line_number_area_width(0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.line_number_area.setGeometry(QRect(cr.left(), cr.top(), self.line_number_area_width(), cr.height()))

    def line_number_area_paint_event(self, event):
        painter = QPainter(self.line_number_area)
        painter.fillRect(event.rect(), QColor(0, 15, 25, 200))

        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = int(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + int(self.blockBoundingRect(block).height())

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(block_number + 1)
                painter.setPen(QColor("#336655" if block_number + 1 != self.textCursor().blockNumber() + 1 else "#00ffaa"))
                painter.setFont(QFont("Consolas", 10))
                painter.drawText(0, top, self.line_number_area.width() - 4,
                                 self.fontMetrics().height(), Qt.AlignRight, number)
            block = block.next()
            top = bottom
            bottom = top + int(self.blockBoundingRect(block).height())
            block_number += 1

    # ── Current line highlight ──
    def highlight_current_line(self):
        extra = []
        if not self.isReadOnly():
            sel = QTextEdit.ExtraSelection()
            sel.format.setBackground(QColor(0, 60, 50, 60))
            sel.format.setProperty(QTextFormat.FullWidthSelection, True)
            sel.cursor = self.textCursor()
            sel.cursor.clearSelection()
            extra.append(sel)
        self.setExtraSelections(extra)

    # ── Key handling: auto-indent, Shift+Enter run, Tab→spaces ──
    def keyPressEvent(self, event):
        # Shift+Enter → run
        if event.key() in (Qt.Key_Return, Qt.Key_Enter) and event.modifiers() == Qt.ShiftModifier:
            self.run_requested.emit()
            return

        # Ctrl+Enter → clear + run
        if event.key() in (Qt.Key_Return, Qt.Key_Enter) and event.modifiers() == Qt.ControlModifier:
            self.run_clear_requested.emit()
            return

        # Tab → 4 spaces
        if event.key() == Qt.Key_Tab:
            cursor = self.textCursor()
            cursor.insertText("    ")
            return

        # Enter → preserve indentation; add extra indent after ':'
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            cursor = self.textCursor()
            cursor.select(QTextCursor.LineUnderCursor)
            line = cursor.selectedText()
            indent = ""
            for ch in line:
                if ch in (' ', '\t'):
                    indent += ch
                else:
                    break
            stripped = line.rstrip()
            extra_indent = "    " if stripped.endswith(":") else ""
            cursor.movePosition(QTextCursor.EndOfLine)
            cursor.insertText("\n" + indent + extra_indent)
            self.setTextCursor(cursor)
            return

        # Backspace: remove up to 4 spaces if only whitespace before cursor
        if event.key() == Qt.Key_Backspace:
            cursor = self.textCursor()
            if not cursor.hasSelection():
                cursor.select(QTextCursor.LineUnderCursor)
                line = cursor.selectedText()
                col = self.textCursor().columnNumber()
                before = line[:col]
                if before and before == " " * len(before) and len(before) % 4 == 0:
                    for _ in range(4):
                        self.textCursor().deletePreviousChar()
                    return

        super().keyPressEvent(event)

    def cursor_position(self):
        c = self.textCursor()
        return c.blockNumber() + 1, c.columnNumber() + 1


# ──────────────────────────────────────────────
# Find / Replace Bar
# ──────────────────────────────────────────────
class FindReplaceBar(QFrame):
    closed = pyqtSignal()

    def __init__(self, editor: CodeEditor, parent=None):
        super().__init__(parent)
        self.editor = editor
        self.setStyleSheet("""
            QFrame {
                background-color: rgba(0,20,30,230);
                border-top: 1px solid rgba(0,255,200,60);
            }
            QLineEdit {
                background: rgba(0,10,20,200);
                color: #00ffcc;
                border: 1px solid rgba(0,255,200,50);
                border-radius: 4px;
                padding: 3px 6px;
                font-family: Consolas; font-size: 11pt;
            }
            QLabel { color: #00ffaa; font-family: Consolas; font-size: 10pt; }
        """)
        self._build_ui()

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(6)

        def btn(text, tip, fn):
            b = QPushButton(text)
            b.setToolTip(tip)
            b.setFixedHeight(24)
            b.setStyleSheet("""
                QPushButton {
                    background: rgba(0,100,80,120); color:#00ffcc;
                    border:1px solid rgba(0,255,200,40); border-radius:4px; padding:0 8px;
                    font-family:Consolas; font-size:10pt;
                }
                QPushButton:hover { background: rgba(0,200,150,120); color:black; }
            """)
            b.clicked.connect(fn)
            return b

        layout.addWidget(QLabel("Find:"))
        self.find_input = QLineEdit()
        self.find_input.setFixedWidth(180)
        self.find_input.returnPressed.connect(self.find_next)
        layout.addWidget(self.find_input)

        layout.addWidget(btn("▲", "Previous", self.find_prev))
        layout.addWidget(btn("▼", "Next",     self.find_next))

        layout.addWidget(QLabel("Replace:"))
        self.replace_input = QLineEdit()
        self.replace_input.setFixedWidth(160)
        layout.addWidget(self.replace_input)

        layout.addWidget(btn("Replace", "Replace current", self.replace_one))
        layout.addWidget(btn("All",     "Replace all",     self.replace_all))

        self.case_cb = QCheckBox("Aa")
        self.case_cb.setStyleSheet("color:#00ffaa; font-family:Consolas;")
        layout.addWidget(self.case_cb)

        self.regex_cb = QCheckBox(".*")
        self.regex_cb.setStyleSheet("color:#00ffaa; font-family:Consolas;")
        layout.addWidget(self.regex_cb)

        self.match_lbl = QLabel("")
        layout.addWidget(self.match_lbl)
        layout.addStretch()

        layout.addWidget(btn("✕", "Close", self.closed.emit))

    def _flags(self):
        flags = QTextDocument.FindFlags()
        if self.case_cb.isChecked():
            flags |= QTextDocument.FindCaseSensitively
        return flags

    def _pattern(self):
        text = self.find_input.text()
        if not self.regex_cb.isChecked():
            text = QRegularExpression.escape(text)
        return text

    def find_next(self):
        self._find(forward=True)

    def find_prev(self):
        self._find(forward=False)

    def _find(self, forward=True):
        from PyQt5.QtGui import QTextDocument
        text = self.find_input.text()
        if not text:
            return
        flags = self._flags()
        if not forward:
            flags |= QTextDocument.FindBackward
        found = self.editor.find(text, flags)
        self.match_lbl.setText("" if found else "Not found")
        self.match_lbl.setStyleSheet(
            "color:#ff5555;" if not found else "color:#00ffaa;"
        )

    def replace_one(self):
        cursor = self.editor.textCursor()
        if cursor.hasSelection() and cursor.selectedText() == self.find_input.text():
            cursor.insertText(self.replace_input.text())
        self.find_next()

    def replace_all(self):
        text = self.find_input.text()
        replacement = self.replace_input.text()
        if not text:
            return
        content = self.editor.toPlainText()
        flags = 0 if self.case_cb.isChecked() else QRegularExpression.CaseInsensitiveOption
        pattern = self._pattern()
        exp = QRegularExpression(pattern)
        exp.setPatternOptions(flags)
        new_content, count = exp.globalMatch(content), 0
        result = content
        it = exp.globalMatch(content)
        # Simple replace via Python
        import re
        re_flags = 0 if self.case_cb.isChecked() else re.IGNORECASE
        pat = text if self.regex_cb.isChecked() else re.escape(text)
        new_content, count = re.subn(pat, replacement, content, flags=re_flags)
        self.editor.setPlainText(new_content)
        self.match_lbl.setText(f"{count} replaced")
        self.match_lbl.setStyleSheet("color:#00ffaa;")


# ──────────────────────────────────────────────
# Editor Tab (wrapper: editor + find bar)
# ──────────────────────────────────────────────
class EditorTab(QWidget):
    def __init__(self, path=None):
        super().__init__()
        self.path     = path
        self.language = detect_language(path)
        self._modified = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.editor = CodeEditor()
        self.highlighter = UniversalHighlighter(self.editor.document(), self.language)

        self.find_bar = FindReplaceBar(self.editor)
        self.find_bar.setVisible(False)
        self.find_bar.closed.connect(lambda: self.find_bar.setVisible(False))

        layout.addWidget(self.editor)
        layout.addWidget(self.find_bar)

        self.editor.document().modificationChanged.connect(self._on_modified)

    def _on_modified(self, modified):
        self._modified = modified

    def is_modified(self):
        return self._modified

    def toggle_find(self):
        self.find_bar.setVisible(not self.find_bar.isVisible())
        if self.find_bar.isVisible():
            self.find_bar.find_input.setFocus()
            sel = self.editor.textCursor().selectedText()
            if sel:
                self.find_bar.find_input.setText(sel)

    def set_language(self, lang: str):
        self.language = lang
        self.highlighter.set_language(lang)

    # Delegate common methods
    def toPlainText(self):   return self.editor.toPlainText()
    def setPlainText(self, t): self.editor.setPlainText(t)
    def document(self):      return self.editor.document()
    def cursor_position(self): return self.editor.cursor_position()
