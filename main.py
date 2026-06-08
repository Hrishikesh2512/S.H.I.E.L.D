"""
main.py — S.H.I.E.L.D. v3.0 IDE  (modular entry point)

Architecture
────────────
main.py                ← this file; ShieldIDE window
core/
  highlighter.py       ← UniversalHighlighter (Python/JS/Bash/C/JSON/MD)
  editor.py            ← EditorTab, CodeEditor (line nums, find/replace, auto-indent)
  project.py           ← ProjectConfig (.shield_config.json per folder)
ui/
  console.py           ← ConsoleWidget (ANSI colors, stdin, kill, scroll lock)
  statusbar.py         ← StatusBar (git branch, CPU/RAM, cursor, time)
  project_dialog.py    ← ProjectSettingsDialog
  ai_panel.py          ← AIPanel (Claude API — Explain / Debug / Refactor / Docs)
"""

import sys
import os

from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QPushButton, QLabel, QFileDialog, QMessageBox,
    QMenuBar, QAction, QTabWidget,
    QFrame, QShortcut,
)
from PyQt5.QtGui import QFont, QColor, QPalette, QKeySequence, QIcon
from PyQt5.QtCore import Qt, QPoint, QModelIndex, QTimer

from core.editor import EditorTab
from core.project import ProjectConfig, load_or_create
from core.highlighter import detect_language, EXTENSION_MAP
from ui.console import ConsoleWidget
from ui.statusbar import StatusBar
from ui.project_dialog import ProjectSettingsDialog
from ui.ai_panel import AIPanel
from ui.explorer import ExplorerWidget




# ──────────────────────────────────────────────
# Main IDE Window
# ──────────────────────────────────────────────
class ShieldIDE(QWidget):
    APP_NAME    = "S.H.I.E.L.D."
    APP_VERSION = "3.0"

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{self.APP_NAME} v{self.APP_VERSION} — Transparent HUD IDE")
        self.setGeometry(180, 100, 1400, 860)
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint | Qt.WindowSystemMenuHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAutoFillBackground(False)

        pal = self.palette()
        pal.setColor(QPalette.Window, QColor(0, 0, 0, 0))
        self.setPalette(pal)

        self.drag_pos        = QPoint()
        self.always_on_top   = False
        self.current_folder  = None
        self.project_config: ProjectConfig = None

        self._setup_ui()
        self._setup_global_shortcuts()

    # ═══════════════════════════════════════════
    # UI Construction
    # ═══════════════════════════════════════════
    def _setup_ui(self):
        # Outer frame with translucent background
        self.frame = QWidget()
        self.frame.setStyleSheet("""
            QWidget#frame {
                background-color: rgba(0, 10, 20, 175);
                border: 1px solid rgba(0,255,255,50);
                border-radius: 14px;
            }
        """)
        self.frame.setObjectName("frame")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self.frame)

        layout = QVBoxLayout(self.frame)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        layout.setMenuBar(self._build_menubar())
        layout.addLayout(self._build_titlebar())
        layout.addWidget(self._build_main_splitter(), stretch=1)
        layout.addWidget(self._build_statusbar())

    # ── Menu Bar ────────────────────────────────
    def _build_menubar(self):
        mb = QMenuBar()
        mb.setStyleSheet("""
            QMenuBar { background-color:rgba(0,0,0,120); color:#00ffff; }
            QMenuBar::item:selected { background:rgba(0,255,255,80); color:black; }
            QMenu { background:rgba(0,12,22,240); color:#00ffff; border:1px solid rgba(0,255,255,40); }
            QMenu::item:selected { background:rgba(0,255,255,80); color:black; }
            QMenu::separator { background:rgba(0,255,255,30); height:1px; margin:3px 10px; }
        """)

        def act(menu, name, shortcut, fn, sep_before=False):
            if sep_before:
                menu.addSeparator()
            a = QAction(name, self)
            if shortcut:
                a.setShortcut(QKeySequence(shortcut))
            a.triggered.connect(fn)
            menu.addAction(a)

        # File
        fm = mb.addMenu("File")
        act(fm, "New File",          "Ctrl+N",       self.action_new_file)
        act(fm, "Open File…",        "Ctrl+O",       self.action_open_file)
        act(fm, "Open Folder…",      "Ctrl+Shift+O", self.action_open_folder)
        act(fm, "Save",              "Ctrl+S",       self.action_save,     sep_before=True)
        act(fm, "Save As…",          "Ctrl+Shift+S", self.action_save_as)
        act(fm, "Close Tab",         "Ctrl+W",       self.action_close_tab, sep_before=True)
        act(fm, "Clear All Tabs",    None,           self.action_clear_all_tabs)
        act(fm, "Exit",              "Alt+F4",       self.close, sep_before=True)

        # Edit
        em = mb.addMenu("Edit")
        act(em, "Find / Replace",    "Ctrl+H",       self.toggle_find_replace)
        act(em, "Find Next",         "F3",           self.find_next)

        # Run
        rm = mb.addMenu("Run")
        act(rm, "Run File",          "Ctrl+R",       self.action_run_current)
        act(rm, "Run + Clear",       "Ctrl+Shift+R", self.action_run_clear)
        act(rm, "Run Entry Point",   "F5",           self.action_run_entry)
        act(rm, "Kill Process",      "Ctrl+K",       self.action_kill)
        act(rm, "Clear Console",     "Ctrl+L",       self.action_clear_console)

        # View
        vm = mb.addMenu("View")
        act(vm, "Toggle Explorer",   "Ctrl+B",       self.toggle_explorer)
        act(vm, "Toggle AI Panel",   "Ctrl+Shift+A", self.toggle_ai_panel)
        act(vm, "Toggle Console",    "Ctrl+`",       self.toggle_console)
        act(vm, "Always on Top",     None,           self.toggle_top)

        # Project
        pm = mb.addMenu("Project")
        act(pm, "Project Settings…", "Ctrl+,",       self.open_project_settings)
        act(pm, "Reload Config",     None,           self.reload_project_config)

        return mb

    # ── Title Bar ───────────────────────────────
    def _build_titlebar(self):
        row = QHBoxLayout()
        self.title_lbl = QLabel(self.APP_NAME)
        self.title_lbl.setFont(QFont("Courier New", 18, QFont.Bold))
        self.title_lbl.setStyleSheet("color:#00ffff; letter-spacing:3px;")
        row.addWidget(self.title_lbl)
        row.addStretch()

        for text, tip, fn in [
            ("📌", "Pin on top",   self.toggle_top),
            ("─",  "Minimize",     self.showMinimized),
            ("□",  "Maximize",     self._toggle_maximize),
            ("×",  "Close",        self.close),
        ]:
            b = QPushButton(text)
            b.setToolTip(tip)
            b.setFixedSize(30, 30)
            b.setStyleSheet(self._btn_style())
            b.clicked.connect(fn)
            row.addWidget(b)
        return row

    # ── Main Splitter ────────────────────────────
    def _build_main_splitter(self):
        self.main_splitter = QSplitter(Qt.Horizontal)
        self.main_splitter.setStyleSheet(
            "QSplitter::handle { background:rgba(0,255,255,30); width:2px; }"
        )

        # Left: file explorer
        self.main_splitter.addWidget(self._build_explorer())

        # Center: tabs + console (vertical splitter)
        self.main_splitter.addWidget(self._build_center())

        # Right: AI panel (hidden by default)
        self.ai_panel = AIPanel()
        self.ai_panel.set_code_getter(self._get_current_code)
        self.ai_panel.setVisible(False)
        self.main_splitter.addWidget(self.ai_panel)

        self.main_splitter.setSizes([230, 970, 0])
        return self.main_splitter

    # ── Explorer ─────────────────────────────────
    def _build_explorer(self):
        self.explorer = ExplorerWidget()
        self.explorer.file_opened.connect(self._open_file_in_tab)
        # Keep a .tree alias so toggle_explorer still works
        self.tree = self.explorer.tree
        return self.explorer

    # ── Center area ──────────────────────────────
    def _build_center(self):
        self.center_splitter = QSplitter(Qt.Vertical)
        self.center_splitter.setStyleSheet(
            "QSplitter::handle { background:rgba(0,255,255,30); height:2px; }"
        )

        # Editor tabs
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self._close_tab_index)
        self.tabs.currentChanged.connect(self._on_tab_changed)
        self.tabs.setStyleSheet("""
            QTabWidget::pane { border:1px solid rgba(0,255,170,50); background:rgba(0,12,22,200); }
            QTabBar::tab {
                background:rgba(0,50,40,100); color:#00ffaa;
                border:1px solid rgba(0,255,170,40); padding:4px 14px;
                font-family:Consolas; font-size:10pt;
            }
            QTabBar::tab:selected { background:rgba(0,180,130,80); color:#ffffff; }
            QTabBar::tab:hover    { background:rgba(0,120,90,80); }
        """)
        self.center_splitter.addWidget(self.tabs)

        # Console
        self.console = ConsoleWidget()
        self.center_splitter.addWidget(self.console)

        self.center_splitter.setSizes([580, 220])
        return self.center_splitter

    # ── Status bar ───────────────────────────────
    def _build_statusbar(self):
        self.statusbar = StatusBar()
        return self.statusbar

    # ═══════════════════════════════════════════
    # Global Shortcuts
    # ═══════════════════════════════════════════
    def _setup_global_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+Tab"),     self, self._next_tab)
        QShortcut(QKeySequence("Ctrl+Shift+Tab"), self, self._prev_tab)
        QShortcut(QKeySequence("F11"),          self, self._toggle_maximize)

    # ═══════════════════════════════════════════
    # File / Tab actions
    # ═══════════════════════════════════════════
    def action_new_file(self):
        editor = EditorTab()
        editor.editor.run_requested.connect(self.action_run_current)
        editor.editor.run_clear_requested.connect(self.action_run_clear)
        editor.editor.cursorPositionChanged.connect(self._update_cursor_status)
        idx = self.tabs.addTab(editor, "untitled")
        self.tabs.setCurrentIndex(idx)

    def action_open_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open File", self.current_folder or "",
            "All Supported (*.py *.js *.ts *.jsx *.tsx *.sh *.c *.cpp *.h *.json *.md *.txt);;"
            "Python (*.py);;JavaScript (*.js *.ts);;All Files (*)"
        )
        if path:
            self._open_file_in_tab(path)

    def action_open_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Open Folder", self.current_folder or "")
        if not folder:
            return
        self.current_folder = folder
        self.project_config = load_or_create(folder)

        # Update explorer
        self.explorer.set_exclude(self.project_config.get("exclude_dirs", []))
        self.explorer.set_root(folder)

        name = self.project_config.get("name") or os.path.basename(folder)
        self.title_lbl.setText(f"{self.APP_NAME} — {name}")
        self.statusbar.set_workspace(folder)
        self.console.append_html(
            f"<b style='color:#00ffaa'>📁 Workspace: {folder}</b><br>"
        )

        # Try to open entry point automatically
        ep = self.project_config.get("entry_point", "")
        if ep:
            full_ep = os.path.join(folder, ep)
            if os.path.isfile(full_ep):
                self._open_file_in_tab(full_ep)

    def action_save(self):
        editor = self._current_editor()
        if not editor:
            return
        if editor.path:
            with open(editor.path, "w", encoding="utf-8") as f:
                f.write(editor.toPlainText())
            editor.document().setModified(False)
            self._update_tab_title(editor)
            self.statusbar.show_message(f"Saved {os.path.basename(editor.path)}", "#00ffaa")
        else:
            self.action_save_as()

    def action_save_as(self):
        editor = self._current_editor()
        if not editor:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Save File As", self.current_folder or "",
            "Python Files (*.py);;All Files (*)"
        )
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(editor.toPlainText())
            editor.path = path
            editor.set_language(detect_language(path))
            self.tabs.setTabText(self.tabs.currentIndex(), os.path.basename(path))
            self.statusbar.show_message(f"Saved as {os.path.basename(path)}", "#00ffaa")

    def action_close_tab(self):
        i = self.tabs.currentIndex()
        if i != -1:
            self._close_tab_index(i)

    def action_clear_all_tabs(self):
        for i in range(self.tabs.count() - 1, -1, -1):
            self.tabs.removeTab(i)
        self.statusbar.show_message("All tabs closed.", "#ffdd88")

    # ═══════════════════════════════════════════
    # Run actions
    # ═══════════════════════════════════════════
    def action_run_current(self):
        editor = self._current_editor()
        if not editor:
            self.console.append_html("<b style='color:#ff5555'>No active editor.</b><br>")
            return

        cfg = self.project_config
        if editor.path:
            # Run saved file
            lang = editor.language
            cmd  = cfg.build_run_command(editor.path, lang) if cfg else [
                sys.executable, "-u", editor.path
            ]
            env = cfg.build_env() if cfg else None
            self.console.run(cmd, env=env, cwd=self.current_folder)
        else:
            # Run buffer via -c (Python only)
            py = cfg.resolve_python() if cfg else sys.executable
            env = cfg.build_env() if cfg else None
            self.console.run_code_string(editor.toPlainText(), py, env)

    def action_run_clear(self):
        self.console.clear()
        self.action_run_current()

    def action_run_entry(self):
        """Run the project's designated entry point."""
        if not self.project_config:
            self.statusbar.show_message("No project open.", "#ff5555")
            return
        entry = self.project_config.resolve_entry()
        if not entry:
            self.statusbar.show_message("No entry point set. Configure in Project Settings.", "#ffaa00")
            return
        lang = detect_language(entry)
        cmd  = self.project_config.build_run_command(entry, lang)
        env  = self.project_config.build_env()
        self.console.run(cmd, env=env, cwd=self.current_folder)

    def action_kill(self):
        self.console.kill_process()

    def action_clear_console(self):
        self.console.clear()

    # ═══════════════════════════════════════════
    # Edit actions
    # ═══════════════════════════════════════════
    def toggle_find_replace(self):
        editor = self._current_editor()
        if editor:
            editor.toggle_find()

    def find_next(self):
        editor = self._current_editor()
        if editor and editor.find_bar.isVisible():
            editor.find_bar.find_next()

    # ═══════════════════════════════════════════
    # View actions
    # ═══════════════════════════════════════════
    def toggle_explorer(self):
        visible = self.explorer.isVisible()
        self.explorer.setVisible(not visible)
        sizes = self.main_splitter.sizes()
        if visible:
            self._explorer_last_width = sizes[0]
            self.main_splitter.setSizes([0] + sizes[1:])
        else:
            w = getattr(self, "_explorer_last_width", 230)
            self.main_splitter.setSizes([w] + sizes[1:])

    def toggle_ai_panel(self):
        visible = self.ai_panel.isVisible()
        self.ai_panel.setVisible(not visible)
        sizes = self.main_splitter.sizes()
        if not visible:
            total = sum(sizes)
            self.main_splitter.setSizes([sizes[0], total - sizes[0] - 360, 360])
        else:
            self.main_splitter.setSizes([sizes[0], sizes[1] + sizes[2], 0])

    def toggle_console(self):
        sizes = self.center_splitter.sizes()
        if sizes[1] > 0:
            self._console_last = sizes[1]
            self.center_splitter.setSizes([sizes[0] + sizes[1], 0])
        else:
            h = getattr(self, "_console_last", 220)
            self.center_splitter.setSizes([sizes[0] - h, h])

    def toggle_top(self):
        self.always_on_top = not self.always_on_top
        self.setWindowFlag(Qt.WindowStaysOnTopHint, self.always_on_top)
        self.show()
        self.statusbar.show_message(
            "Pinned on top" if self.always_on_top else "Unpinned", "#aaddff"
        )

    # ═══════════════════════════════════════════
    # Project actions
    # ═══════════════════════════════════════════
    def open_project_settings(self):
        if not self.project_config:
            if not self.current_folder:
                QMessageBox.information(self, "No Project", "Open a folder first.")
                return
            self.project_config = load_or_create(self.current_folder)
        dlg = ProjectSettingsDialog(self.project_config, self)
        if dlg.exec_():
            self.reload_project_config()

    def reload_project_config(self):
        if self.project_config:
            self.project_config.load()
            self.explorer.set_exclude(self.project_config.get("exclude_dirs", []))
            self.statusbar.show_message("Project config reloaded.", "#00ffaa")

    # ═══════════════════════════════════════════
    # Internal helpers
    # ═══════════════════════════════════════════
    def _open_file_in_tab(self, path):
        # Switch to existing tab if already open
        for i in range(self.tabs.count()):
            w = self.tabs.widget(i)
            if isinstance(w, EditorTab) and w.path == path:
                self.tabs.setCurrentIndex(i)
                return
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
            return

        editor = EditorTab(path)
        editor.setPlainText(content)
        editor.editor.run_requested.connect(self.action_run_current)
        editor.editor.run_clear_requested.connect(self.action_run_clear)
        editor.editor.cursorPositionChanged.connect(self._update_cursor_status)

        idx = self.tabs.addTab(editor, os.path.basename(path))
        self.tabs.setCurrentIndex(idx)
        self.statusbar.set_language(editor.language)

    def _close_tab_index(self, index):
        w = self.tabs.widget(index)
        if isinstance(w, EditorTab) and w.is_modified():
            name = os.path.basename(w.path) if w.path else "untitled"
            r = QMessageBox.question(
                self, "Unsaved Changes",
                f"'{name}' has unsaved changes. Save before closing?",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel
            )
            if r == QMessageBox.Cancel:
                return
            if r == QMessageBox.Save:
                self.tabs.setCurrentIndex(index)
                self.action_save()
        self.tabs.removeTab(index)

    def _current_editor(self):
        w = self.tabs.currentWidget()
        return w if isinstance(w, EditorTab) else None

    def _get_current_code(self) -> str:
        editor = self._current_editor()
        return editor.toPlainText() if editor else ""

    def _update_tab_title(self, editor: EditorTab):
        for i in range(self.tabs.count()):
            if self.tabs.widget(i) is editor:
                name = os.path.basename(editor.path) if editor.path else "untitled"
                modified = "● " if editor.is_modified() else ""
                self.tabs.setTabText(i, modified + name)
                return

    def _on_tab_changed(self, index):
        w = self.tabs.widget(index)
        if isinstance(w, EditorTab):
            self.statusbar.set_language(w.language)
            ln, col = w.cursor_position()
            self.statusbar.set_cursor(ln, col)

    def _update_cursor_status(self):
        editor = self._current_editor()
        if editor:
            ln, col = editor.cursor_position()
            self.statusbar.set_cursor(ln, col)

    def _next_tab(self):
        i = self.tabs.currentIndex()
        self.tabs.setCurrentIndex((i + 1) % max(1, self.tabs.count()))

    def _prev_tab(self):
        i = self.tabs.currentIndex()
        self.tabs.setCurrentIndex((i - 1) % max(1, self.tabs.count()))

    def _toggle_maximize(self):
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    # ── Window dragging (frameless) ──────────────
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton and e.y() < 60:
            self.drag_pos = e.globalPos() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if e.buttons() & Qt.LeftButton and hasattr(self, "drag_pos") and not self.drag_pos.isNull():
            self.move(e.globalPos() - self.drag_pos)

    def mouseReleaseEvent(self, e):
        self.drag_pos = QPoint()

    # ── Styles ───────────────────────────────────
    def _btn_style(self):
        return """
            QPushButton {
                background:rgba(0,0,0,170); color:#00ffff;
                border:1px solid rgba(0,255,255,50); border-radius:6px; padding:4px 8px;
                font-family:Consolas; font-size:12pt;
            }
            QPushButton:hover { background:rgba(0,255,255,90); color:black; }
        """


# ──────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # Dark Fusion palette base
    palette = QPalette()
    palette.setColor(QPalette.Window,          QColor(0, 10, 20))
    palette.setColor(QPalette.WindowText,      QColor(0, 255, 200))
    palette.setColor(QPalette.Base,            QColor(0, 15, 25))
    palette.setColor(QPalette.AlternateBase,   QColor(0, 20, 35))
    palette.setColor(QPalette.ToolTipBase,     QColor(0, 20, 30))
    palette.setColor(QPalette.ToolTipText,     QColor(0, 255, 200))
    palette.setColor(QPalette.Text,            QColor(0, 255, 200))
    palette.setColor(QPalette.Button,          QColor(0, 20, 30))
    palette.setColor(QPalette.ButtonText,      QColor(0, 255, 200))
    palette.setColor(QPalette.BrightText,      QColor(255, 255, 255))
    palette.setColor(QPalette.Highlight,       QColor(0, 180, 130))
    palette.setColor(QPalette.HighlightedText, QColor(0, 0, 0))
    app.setPalette(palette)

    win = ShieldIDE()
    win.show()
    sys.exit(app.exec_())
