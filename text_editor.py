##############################################
#S.H.I.E.L.D. v2.1T — Transparent HUD Edition#
##############################################


import sys
import os
import subprocess
import threading
import datetime
import psutil

from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QTextEdit, QPushButton, QLabel, QFileDialog, QMessageBox,
    QMenuBar, QAction, QTreeView, QFileSystemModel, QTabWidget
)
from PyQt5.QtGui import QFont, QColor, QSyntaxHighlighter, QTextCharFormat, QKeySequence, QPalette, QTextCursor
from PyQt5.QtCore import Qt, QTimer, QPoint, QRegularExpression, QModelIndex


# ==================================================
# Syntax Highlighter
# ==================================================
class PythonHighlighter(QSyntaxHighlighter):
    def __init__(self, document):
        super().__init__(document)

        # -----------------------
        # Define formats
        # -----------------------
        self.keyword_format = QTextCharFormat()
        self.keyword_format.setForeground(QColor("#00FFFF"))  # cyan
        self.keyword_format.setFontWeight(QFont.Bold)

        self.string_format = QTextCharFormat()
        self.string_format.setForeground(QColor("#ffaa00"))  # orange

        self.comment_format = QTextCharFormat()
        self.comment_format.setForeground(QColor("#55ff55"))  # green

        self.number_format = QTextCharFormat()
        self.number_format.setForeground(QColor("#ff66ff"))  # pink

        self.func_format = QTextCharFormat()
        self.func_format.setForeground(QColor("#ffaa00"))  # orange

        self.class_format = QTextCharFormat()
        self.class_format.setForeground(QColor("#00ff66"))  # light green

        self.decorator_format = QTextCharFormat()
        self.decorator_format.setForeground(QColor("#ff55ff"))  # purple

        # -----------------------
        # Keywords
        # -----------------------
        self.keywords = [
            'def', 'class', 'if', 'else', 'elif', 'while', 'for', 'try', 'except',
            'import', 'from', 'as', 'return', 'break', 'continue', 'with', 'lambda',
            'pass', 'yield', 'True', 'False', 'None', 'and', 'or', 'not', 'in', 'is'
        ]

    def highlightBlock(self, text):
        # -----------------------
        # Keywords
        # -----------------------
        for word in self.keywords:
            exp = QRegularExpression(r'\b' + word + r'\b')
            it = exp.globalMatch(text)
            while it.hasNext():
                m = it.next()
                self.setFormat(m.capturedStart(), m.capturedLength(), self.keyword_format)

        # -----------------------
        # Strings
        # -----------------------
        string_exp = QRegularExpression(r'"[^"\\]*(\\.[^"\\]*)*"|\'[^\'\\]*(\\.[^\'\\]*)*\'')
        it = string_exp.globalMatch(text)
        while it.hasNext():
            m = it.next()
            self.setFormat(m.capturedStart(), m.capturedLength(), self.string_format)

        # -----------------------
        # Comments
        # -----------------------
        idx = text.find("#")
        if idx != -1:
            self.setFormat(idx, len(text) - idx, self.comment_format)

        # -----------------------
        # Numbers
        # -----------------------
        number_exp = QRegularExpression(r'\b\d+(\.\d+)?\b')
        it = number_exp.globalMatch(text)
        while it.hasNext():
            m = it.next()
            self.setFormat(m.capturedStart(), m.capturedLength(), self.number_format)

        # -----------------------
        # Function definitions
        # -----------------------
        func_exp = QRegularExpression(r'\bdef\s+(\w+)\b')
        it = func_exp.globalMatch(text)
        while it.hasNext():
            m = it.next()
            self.setFormat(m.capturedStart(1), m.capturedLength(1), self.func_format)

        # Function calls
        call_exp = QRegularExpression(r'\b(\w+)\s*(?=\()')
        it = call_exp.globalMatch(text)
        while it.hasNext():
            m = it.next()
            self.setFormat(m.capturedStart(1), m.capturedLength(1), self.func_format)

        # -----------------------
        # Class names
        # -----------------------
        class_exp = QRegularExpression(r'\bclass\s+(\w+)\b')
        it = class_exp.globalMatch(text)
        while it.hasNext():
            m = it.next()
            self.setFormat(m.capturedStart(1), m.capturedLength(1), self.class_format)

        # -----------------------
        # Decorators
        # -----------------------
        decorator_exp = QRegularExpression(r'@\w+')
        it = decorator_exp.globalMatch(text)
        while it.hasNext():
            m = it.next()
            self.setFormat(m.capturedStart(), m.capturedLength(), self.decorator_format)

# ==================================================
# Editor Tab
# ==================================================
class EditorTab(QTextEdit):
    def __init__(self, path=None):
        super().__init__()
        self.path = path
        self.setFont(QFont("Consolas", 12))
        self.setStyleSheet("""
            QTextEdit {
                background-color: rgba(5,10,20,200);
                color: #00ffcc;
                border: 1px solid #00ffaa;
                border-radius: 8px;
                padding: 8px;
            }
        """)
        self.highlighter = PythonHighlighter(self.document())

    # ---------------------------
    # Auto indentation (VS Code style)
    # ---------------------------
    def keyPressEvent(self, event):
    # --- Shift + Enter: Run ---
        if event.key() in (Qt.Key_Return, Qt.Key_Enter) and event.modifiers() == Qt.ShiftModifier:
            parent = self.parent()
            while parent and not hasattr(parent, "action_run_current"):
                parent = parent.parent()
            if parent and hasattr(parent, "action_run_current"):
                parent.action_run_current()
            return

    # --- Ctrl + Enter: Clear + Run ---
        if event.key() in (Qt.Key_Return, Qt.Key_Enter) and event.modifiers() == Qt.ControlModifier:
            parent = self.parent()
            while parent and not hasattr(parent, "action_run_clear"):
                parent = parent.parent()
            if parent and hasattr(parent, "action_run_clear"):
                parent.action_run_clear()
            return

    # --- Normal Enter behavior (Just add a new line like VS Code) ---
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            cursor = self.textCursor()
            cursor.beginEditBlock()

        # Get the current line under the cursor
            cursor.select(QTextCursor.LineUnderCursor)
            line_text = cursor.selectedText()

        # Get indentation of the current line
            indentation = ""
            for ch in line_text:
                if ch == ' ' or ch == '\t':
                    indentation += ch
                else:
                    break

        # Insert new line and keep the same indentation
            cursor.movePosition(QTextCursor.EndOfLine)  # Move to the end of the current line
            cursor.insertText("\n" + indentation)  # Create a new line with the same indentation

            self.setTextCursor(cursor)
            cursor.endEditBlock()
        else:
            super().keyPressEvent(event)

# ==================================================
# Main IDE Class
# ==================================================
class ShieldIDE(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("S.H.I.E.L.D. — Transparent HUD IDE")
        self.setGeometry(200, 120, 1200, 800)
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint | Qt.WindowSystemMenuHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAutoFillBackground(False)

        palette = self.palette()
        palette.setColor(QPalette.Window, QColor(0, 0, 0, 0))
        self.setPalette(palette)

        self.drag_pos = QPoint()
        self.always_on_top = False
        self.current_folder = None

        self._setup_ui()

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_status)
        self.timer.start(1000)

    # ---------------------------
    def _setup_ui(self):
        frame = QWidget()
        frame.setStyleSheet("""
            QWidget {
                background-color: rgba(0, 10, 20, 160);
                border: 1px solid rgba(0,255,255,60);
                border-radius: 12px;
            }
        """)

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(8, 8, 8, 8)

        # === Menu Bar ===
        menubar = QMenuBar()
        menubar.setStyleSheet("""
            QMenuBar {
                background-color: rgba(0,0,0,100);
                color: #00ffff;
            }
            QMenuBar::item:selected {
                background-color: rgba(0,255,255,80);
                color: black;
            }
            QMenu {
                background-color: rgba(0,10,20,230);
                color: #00ffff;
            }
            QMenu::item:selected {
                background-color: rgba(0,255,255,100);
                color: black;
            }
        """)

        file_menu = menubar.addMenu("File")
        run_menu = menubar.addMenu("Run")
        view_menu = menubar.addMenu("View")
        tools_menu = menubar.addMenu("Tools")

        def add_action(menu, name, shortcut, func):
            act = QAction(name, self)
            if shortcut:
                act.setShortcut(QKeySequence(shortcut))
            act.triggered.connect(func)
            menu.addAction(act)
            return act

        # File actions
        add_action(file_menu, "New", "Ctrl+N", self.action_new_file)
        add_action(file_menu, "Open File...", "Ctrl+O", self.action_open_file)
        add_action(file_menu, "Open Folder...", "Ctrl+Shift+O", self.action_open_folder)
        add_action(file_menu, "Save", "Ctrl+S", self.action_save)
        add_action(file_menu, "Save As...", "Ctrl+Shift+S", self.action_save_as)
        add_action(file_menu, "Close Tab", "Ctrl+W", self.action_close_tab)
        file_menu.addSeparator()
        add_action(file_menu, "Clear All Tabs", None, self.action_clear_all_tabs)
        add_action(file_menu, "Exit", "Alt+F4", self.close)

        # Run actions
        add_action(run_menu, "Run File", "Ctrl+R", self.action_run_current)
        add_action(run_menu, "Run + Clear", "Ctrl+Shift+R", self.action_run_clear)
        add_action(run_menu, "Clear Console", "Ctrl+L", self.clear_console)

        # View actions
        add_action(view_menu, "Toggle Explorer", "Ctrl+B", self.toggle_explorer)

        # Tools actions
        add_action(tools_menu, "Clear Console", "Ctrl+L", self.clear_console)
        add_action(tools_menu, "Run + Clear", "Ctrl+Shift+R", self.action_run_clear)

        layout.setMenuBar(menubar)

        # === Title Bar ===
        title_layout = QHBoxLayout()
        self.title_lbl = QLabel("S.H.I.E.L.D.")
        self.title_lbl.setFont(QFont("Orbitron", 20, QFont.Bold))
        self.title_lbl.setStyleSheet("color: #00ffff; letter-spacing: 2px;")
        title_layout.addWidget(self.title_lbl)
        title_layout.addStretch()

        self.pin_btn = QPushButton("📌")
        self.pin_btn.setFixedSize(30, 30)
        self.pin_btn.setStyleSheet(self._btn_style())
        self.pin_btn.clicked.connect(self.toggle_top)

        self.close_btn = QPushButton("×")
        self.close_btn.setFixedSize(30, 30)
        self.close_btn.setStyleSheet(self._btn_style())
        self.close_btn.clicked.connect(self.close)

        title_layout.addWidget(self.pin_btn)
        title_layout.addWidget(self.close_btn)
        layout.addLayout(title_layout)

        # === Splitter ===
        splitter = QSplitter(Qt.Horizontal)
        splitter.setStyleSheet("QSplitter::handle { background-color: rgba(0,255,255,40); }")

        # File Explorer
        self.model = QFileSystemModel()
        self.model.setRootPath("")
        self.tree = QTreeView()
        self.tree.setModel(self.model)
        self.tree.hideColumn(1)
        self.tree.hideColumn(2)
        self.tree.hideColumn(3)
        self.tree.setHeaderHidden(True)
        self.tree.clicked.connect(self.on_tree_clicked)
        self.tree.setStyleSheet("""
            QTreeView {
                background-color: rgba(0, 20, 30, 150);
                color: #00ffff;
                border: 1px solid rgba(0,255,255,80);
                border-radius: 6px;
            }
        """)
        splitter.addWidget(self.tree)

        # Tabs + Console (Right)
        right_layout = QVBoxLayout()
        right_layout.setContentsMargins(0, 0, 0, 0)

        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab_index)
        self.tabs.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #00ffaa; background: rgba(0,15,25,200); }
            QTabBar::tab {
                background: rgba(0,255,255,30);
                color: #00ffaa;
                border: 1px solid rgba(0,255,255,50);
                padding: 4px 12px;
            }
            QTabBar::tab:selected { background: rgba(0,255,255,80); color: black; }
        """)
        right_layout.addWidget(self.tabs, 7)

        self.console = QTextEdit(readOnly=True)
        self.console.setFont(QFont("Consolas", 11))
        self.console.setStyleSheet("""
            QTextEdit {
                background-color: rgba(0, 20, 30, 200);
                color: #aaffcc;
                border: 1px solid #00ffaa;
                border-radius: 6px;
                padding: 8px;
            }
        """)
        right_layout.addWidget(self.console, 3)

        # Bottom bar
        bottom = QHBoxLayout()
        self.run_btn = QPushButton("▶ Run")
        self.run_btn.setStyleSheet(self._btn_style())
        self.run_btn.clicked.connect(self.action_run_current)

        self.run_clear_btn = QPushButton("🧹▶ Run + Clear")
        self.run_clear_btn.setStyleSheet(self._btn_style())
        self.run_clear_btn.clicked.connect(self.action_run_clear)

        self.clear_btn = QPushButton("🧹 Clear")
        self.clear_btn.setStyleSheet(self._btn_style())
        self.clear_btn.clicked.connect(self.clear_console)

        self.save_btn = QPushButton("💾 Save")
        self.save_btn.setStyleSheet(self._btn_style())
        self.save_btn.clicked.connect(self.action_save)

        self.status_lbl = QLabel("Initializing...")
        self.status_lbl.setStyleSheet("color:#00ffaa; font-family:Consolas;")
        bottom.addWidget(self.run_btn)
        bottom.addWidget(self.run_clear_btn)
        bottom.addWidget(self.clear_btn)
        bottom.addWidget(self.save_btn)
        bottom.addStretch()
        bottom.addWidget(self.status_lbl)
        right_layout.addLayout(bottom)

        right_widget = QWidget()
        right_widget.setLayout(right_layout)
        splitter.addWidget(right_widget)
        splitter.setSizes([250, 950])
        layout.addWidget(splitter)

        root = QVBoxLayout(self)
        root.addWidget(frame)
        self.setLayout(root)

        self.splitter = splitter

    # ---------------------------
    def _btn_style(self):
        return """
            QPushButton {
                background-color: rgba(0,0,0,160);
                color: #00ffff;
                border: 1px solid #00ffff;
                border-radius: 6px;
                padding: 6px 10px;
            }
            QPushButton:hover {
                background-color: rgba(0,255,255,100);
                color: black;
            }
        """

    # ---------------------------
    # Core Functions
    # ---------------------------
    def on_tree_clicked(self, index: QModelIndex):
        path = self.model.filePath(index)
        if os.path.isfile(path):
            self.open_file_in_tab(path)

    def open_file_in_tab(self, path):
        for i in range(self.tabs.count()):
            w = self.tabs.widget(i)
            if isinstance(w, EditorTab) and w.path == path:
                self.tabs.setCurrentIndex(i)
                return
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            editor = EditorTab(path)
            editor.setPlainText(content)
            idx = self.tabs.addTab(editor, os.path.basename(path))
            self.tabs.setCurrentIndex(idx)
            self.console.append(f"<b style='color:#00ffaa'>Opened: {path}</b>")
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def close_tab_index(self, index):
        self.tabs.removeTab(index)

    def action_new_file(self):
        editor = EditorTab()
        idx = self.tabs.addTab(editor, "untitled")
        self.tabs.setCurrentIndex(idx)

    def action_open_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open File", "", "Python Files (*.py);;All Files (*)")
        if path:
            self.open_file_in_tab(path)

    def action_open_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Open Folder", "")
        if folder:
            self.current_folder = folder
            self.model.setRootPath(folder)
            self.tree.setRootIndex(self.model.index(folder))
            self.title_lbl.setText(f"S.H.I.E.L.D. — {os.path.basename(folder)}")
            self.console.append(f"<b style='color:#00ffaa'>Workspace: {folder}</b>")

    def action_save(self):
        editor = self._current_editor()
        if not editor:
            return
        if editor.path:
            with open(editor.path, "w", encoding="utf-8") as f:
                f.write(editor.toPlainText())
            editor.document().setModified(False)
            self.console.append(f"<b style='color:#00ffaa'>Saved: {editor.path}</b>")
        else:
            self.action_save_as()

    def action_save_as(self):
        editor = self._current_editor()
        if not editor:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Save File As", "", "Python Files (*.py);;All Files (*)")
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(editor.toPlainText())
            editor.path = path
            self.tabs.setTabText(self.tabs.currentIndex(), os.path.basename(path))
            self.console.append(f"<b style='color:#00ffaa'>Saved as: {path}</b>")

    def _current_editor(self):
        w = self.tabs.currentWidget()
        return w if isinstance(w, EditorTab) else None

    def action_close_tab(self):
        i = self.tabs.currentIndex()
        if i != -1:
            self.close_tab_index(i)

    def action_clear_all_tabs(self):
        self.tabs.clear()
        self.console.append("<b style='color:#ffcc00'>All tabs cleared.</b>")

    def clear_console(self):
        self.console.clear()

    def action_run_clear(self):
        self.clear_console()
        self.action_run_current()

    def action_run_current(self):
        editor = self._current_editor()
        if not editor:
            self.console.append("<b style='color:#ff5555'>No active editor.</b>")
            return
        code = editor.toPlainText()
        self.console.append("<b style='color:#00ffff'>Running...</b>")

        def run():
            try:
                # --- One more indentation level added here ---
                process = subprocess.Popen(
                    [sys.executable, "-u", "-c", code],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                while True:
                    output = process.stdout.readline()
                    error = process.stderr.readline()
                    if output:
                        self.console.append(f"<pre style='color:#aaffcc'>{output.strip()}</pre>")
                    if error:
                        self.console.append(f"<pre style='color:#ff9999'>{error.strip()}</pre>")
                    if output == "" and error == "" and process.poll() is not None:
                        break
            except Exception as e:
                self.console.append(f"<b style='color:#ff5555'>Error: {e}</b>")

        threading.Thread(target=run, daemon=True).start()


    # ---------------------------
    # Utility
    # ---------------------------
    def toggle_explorer(self):
        self.tree.setVisible(not self.tree.isVisible())

    def toggle_top(self):
        self.always_on_top = not self.always_on_top
        self.setWindowFlag(Qt.WindowStaysOnTopHint, self.always_on_top)
        self.show()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.drag_pos = e.globalPos() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if e.buttons() & Qt.LeftButton:
            self.move(e.globalPos() - self.drag_pos)

    def update_status(self):
        cpu = psutil.cpu_percent()
        ram = psutil.virtual_memory().percent
        now = datetime.datetime.now().strftime("%H:%M:%S")
        workspace = os.path.basename(self.current_folder) if self.current_folder else "(no workspace)"
        self.status_lbl.setText(f"🌐 {workspace} | 🧠 CPU: {cpu}% | 💾 RAM: {ram}% | ⏰ {now}")


# ==================================================
# Entry
# ==================================================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    win = ShieldIDE()
    win.show()
    sys.exit(app.exec_())
