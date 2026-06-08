"""
ui/explorer.py — S.H.I.E.L.D. File Explorer

Features
────────
• Right-click context menu on files AND folders:
    New File / New Folder / Rename (F2) / Delete (Del)
    Duplicate / Cut (Ctrl+X) / Copy (Ctrl+C) / Paste (Ctrl+V)
    Copy Path / Reveal in File Manager
• Inline rename (press F2 or double-click the name area via context menu)
• Drag-and-drop move (within the tree)
• Toolbar: New File  New Folder  Refresh  Collapse All
• Emits  file_opened(path)  signal so the IDE can open tabs
• Respects exclude_dirs filter from project config
"""

import os
import shutil
import platform
import subprocess

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTreeView, QFileSystemModel,
    QPushButton, QLabel, QMenu, QAction, QInputDialog, QMessageBox,
    QAbstractItemView, QToolButton, QSizePolicy,
)
from PyQt5.QtGui import QFont, QColor, QKeySequence, QCursor
from PyQt5.QtCore import (
    Qt, QModelIndex, QSortFilterProxyModel, pyqtSignal, QDir, QFile, QFileInfo,
)


# ──────────────────────────────────────────────
# Filtered proxy model
# ──────────────────────────────────────────────
class _FilterProxy(QSortFilterProxyModel):
    def __init__(self):
        super().__init__()
        self._exclude: set = {".git", "__pycache__", "node_modules", ".idea", ".venv", "venv"}

    def set_exclude(self, dirs):
        self._exclude = set(dirs)
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row, source_parent):
        idx  = self.sourceModel().index(source_row, 0, source_parent)
        name = self.sourceModel().fileName(idx)
        return name not in self._exclude


# ──────────────────────────────────────────────
# Explorer Widget
# ──────────────────────────────────────────────
class ExplorerWidget(QWidget):
    """Emitted when user clicks a file."""
    file_opened = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._root_path   = ""
        self._clipboard   = None   # {"op": "cut"|"copy", "path": str}

        self._fs = QFileSystemModel()
        self._fs.setRootPath(QDir.rootPath())
        self._fs.setReadOnly(False)  # allow rename via model

        self._proxy = _FilterProxy()
        self._proxy.setSourceModel(self._fs)

        self._build_ui()

    # ═══════════════════════════════════════════
    # UI
    # ═══════════════════════════════════════════
    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(self._build_toolbar())
        layout.addWidget(self._build_tree())

    def _build_toolbar(self):
        bar = QWidget()
        bar.setStyleSheet("background:rgba(0,10,20,180); border-bottom:1px solid rgba(0,255,200,30);")
        row = QHBoxLayout(bar)
        row.setContentsMargins(4, 3, 4, 3)
        row.setSpacing(2)

        def tb(icon, tip, fn):
            b = QToolButton()
            b.setText(icon)
            b.setToolTip(tip)
            b.setFixedSize(26, 26)
            b.setStyleSheet("""
                QToolButton {
                    background:transparent; color:#00ffcc;
                    border:none; border-radius:4px; font-size:13pt;
                }
                QToolButton:hover { background:rgba(0,255,200,40); }
                QToolButton:pressed { background:rgba(0,255,200,70); }
            """)
            b.clicked.connect(fn)
            return b

        row.addWidget(tb("📄", "New File  (Ctrl+Alt+N)",    self.action_new_file))
        row.addWidget(tb("📁", "New Folder (Ctrl+Alt+Shift+N)", self.action_new_folder))
        row.addWidget(tb("🔄", "Refresh",                   self.action_refresh))
        row.addWidget(tb("⬆",  "Collapse All",              self.action_collapse_all))
        row.addStretch()
        return bar

    def _build_tree(self):
        self.tree = QTreeView()
        self.tree.setModel(self._proxy)
        for col in (1, 2, 3):
            self.tree.hideColumn(col)
        self.tree.setHeaderHidden(True)
        self.tree.setEditTriggers(QAbstractItemView.NoEditTriggers)  # we handle rename ourselves
        self.tree.setDragDropMode(QAbstractItemView.InternalMove)
        self.tree.setDefaultDropAction(Qt.MoveAction)
        self.tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._show_context_menu)
        self.tree.clicked.connect(self._on_click)
        self.tree.doubleClicked.connect(self._on_double_click)
        self.tree.setStyleSheet("""
            QTreeView {
                background: rgba(0,12,22,170);
                color: #00ffcc;
                border: none;
                font-family: Consolas;
                font-size: 10pt;
            }
            QTreeView::item { padding: 2px 0px; }
            QTreeView::item:hover    { background: rgba(0,255,200,25); }
            QTreeView::item:selected { background: rgba(0,200,150,55); color:#ffffff; }
            QTreeView::branch:has-children:!has-siblings:closed,
            QTreeView::branch:closed:has-children:has-siblings {
                image: none;
            }
        """)
        return self.tree

    # ═══════════════════════════════════════════
    # Public API
    # ═══════════════════════════════════════════
    def set_root(self, path: str):
        self._root_path = path
        src_index   = self._fs.setRootPath(path)
        proxy_index = self._proxy.mapFromSource(src_index)
        self.tree.setRootIndex(proxy_index)

    def set_exclude(self, dirs):
        self._proxy.set_exclude(dirs)

    def refresh(self):
        if self._root_path:
            self.set_root(self._root_path)

    # ═══════════════════════════════════════════
    # Context Menu
    # ═══════════════════════════════════════════
    def _show_context_menu(self, pos):
        proxy_index = self.tree.indexAt(pos)
        path = self._path_at(proxy_index) if proxy_index.isValid() else self._root_path

        is_file = os.path.isfile(path) if path else False
        is_dir  = os.path.isdir(path)  if path else False
        has_sel = bool(path)

        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background: rgba(0,12,22,245);
                color: #00ffcc;
                border: 1px solid rgba(0,255,200,60);
                border-radius: 6px;
                padding: 4px 0px;
                font-family: Consolas;
                font-size: 10pt;
            }
            QMenu::item { padding: 5px 24px 5px 16px; border-radius:3px; }
            QMenu::item:selected { background: rgba(0,200,150,80); color:#ffffff; }
            QMenu::separator { background: rgba(0,255,200,30); height:1px; margin: 4px 8px; }
        """)

        def add(label, fn, shortcut=None, icon=None, enabled=True):
            text = f"{icon}  {label}" if icon else label
            a = QAction(text, self)
            if shortcut:
                a.setShortcut(shortcut)
            a.triggered.connect(fn)
            a.setEnabled(enabled)
            menu.addAction(a)
            return a

        # ── New ──────────────────────────────────
        add("New File",          self.action_new_file,   icon="📄")
        add("New Folder",        self.action_new_folder, icon="📁")
        menu.addSeparator()

        # ── File-level ops ───────────────────────
        if is_file:
            add("Open",          lambda: self.file_opened.emit(path), icon="↗")
            add("Duplicate",     lambda: self._duplicate(path),       icon="⧉")
            menu.addSeparator()

        if has_sel:
            add("Rename",        lambda: self._rename(proxy_index),   icon="✏", shortcut="F2")
            add("Delete",        lambda: self._delete([path]),        icon="🗑", shortcut="Del")
            menu.addSeparator()

        # ── Clipboard ────────────────────────────
        if has_sel:
            add("Cut",           lambda: self._cut(path),   icon="✂")
            add("Copy",          lambda: self._copy(path),  icon="⎘")

        paste_enabled = self._clipboard is not None and bool(self._root_path)
        paste_target  = path if is_dir else (os.path.dirname(path) if path else self._root_path)
        add("Paste",             lambda: self._paste(paste_target), icon="📋", enabled=paste_enabled)

        if has_sel:
            menu.addSeparator()
            add("Copy Path",     lambda: self._copy_path(path),  icon="🔗")
            add("Copy Rel. Path",lambda: self._copy_rel_path(path), icon="🔗")
            menu.addSeparator()
            add("Reveal in File Manager", lambda: self._reveal(path), icon="🗂")

        menu.exec_(QCursor.pos())

    # ═══════════════════════════════════════════
    # Toolbar actions
    # ═══════════════════════════════════════════
    def action_new_file(self):
        target_dir = self._selected_dir() or self._root_path
        if not target_dir:
            return
        name, ok = QInputDialog.getText(self, "New File", "File name:", text="untitled.py")
        if not ok or not name.strip():
            return
        path = os.path.join(target_dir, name.strip())
        if os.path.exists(path):
            QMessageBox.warning(self, "Exists", f"'{name}' already exists.")
            return
        try:
            open(path, "w").close()
            self._fs.setRootPath(self._root_path)  # nudge refresh
            self.file_opened.emit(path)
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def action_new_folder(self):
        target_dir = self._selected_dir() or self._root_path
        if not target_dir:
            return
        name, ok = QInputDialog.getText(self, "New Folder", "Folder name:", text="new_folder")
        if not ok or not name.strip():
            return
        path = os.path.join(target_dir, name.strip())
        if os.path.exists(path):
            QMessageBox.warning(self, "Exists", f"'{name}' already exists.")
            return
        try:
            os.makedirs(path)
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def action_refresh(self):
        self._fs.setRootPath(self._root_path)

    def action_collapse_all(self):
        self.tree.collapseAll()

    # ═══════════════════════════════════════════
    # File operations
    # ═══════════════════════════════════════════
    def _rename(self, proxy_index: QModelIndex):
        if not proxy_index.isValid():
            return
        path = self._path_at(proxy_index)
        old_name = os.path.basename(path)
        new_name, ok = QInputDialog.getText(self, "Rename", "New name:", text=old_name)
        if not ok or not new_name.strip() or new_name.strip() == old_name:
            return
        new_path = os.path.join(os.path.dirname(path), new_name.strip())
        if os.path.exists(new_path):
            QMessageBox.warning(self, "Exists", f"'{new_name}' already exists.")
            return
        try:
            os.rename(path, new_path)
        except Exception as e:
            QMessageBox.critical(self, "Rename Failed", str(e))

    def _delete(self, paths: list):
        if not paths:
            return
        names = "\n".join(os.path.basename(p) for p in paths)
        msg = f"Permanently delete?\n\n{names}"
        r = QMessageBox.warning(
            self, "Delete", msg,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if r != QMessageBox.Yes:
            return
        errors = []
        for path in paths:
            try:
                if os.path.isdir(path):
                    shutil.rmtree(path)
                else:
                    os.remove(path)
            except Exception as e:
                errors.append(f"{os.path.basename(path)}: {e}")
        if errors:
            QMessageBox.critical(self, "Delete Error", "\n".join(errors))

    def _duplicate(self, path: str):
        base, ext = os.path.splitext(os.path.basename(path))
        parent    = os.path.dirname(path)
        # Find a non-colliding name: file_copy.py, file_copy2.py …
        candidate = os.path.join(parent, f"{base}_copy{ext}")
        n = 2
        while os.path.exists(candidate):
            candidate = os.path.join(parent, f"{base}_copy{n}{ext}")
            n += 1
        try:
            if os.path.isdir(path):
                shutil.copytree(path, candidate)
            else:
                shutil.copy2(path, candidate)
        except Exception as e:
            QMessageBox.critical(self, "Duplicate Failed", str(e))

    # ── Clipboard ────────────────────────────────
    def _cut(self, path: str):
        self._clipboard = {"op": "cut", "path": path}

    def _copy(self, path: str):
        self._clipboard = {"op": "copy", "path": path}

    def _paste(self, target_dir: str):
        if not self._clipboard or not os.path.isdir(target_dir):
            return
        src  = self._clipboard["path"]
        op   = self._clipboard["op"]
        name = os.path.basename(src)
        dst  = os.path.join(target_dir, name)

        # Avoid clobbering
        if os.path.exists(dst):
            base, ext = os.path.splitext(name)
            n = 2
            while os.path.exists(dst):
                dst = os.path.join(target_dir, f"{base}_{n}{ext}")
                n  += 1

        try:
            if op == "cut":
                shutil.move(src, dst)
                self._clipboard = None
            else:
                if os.path.isdir(src):
                    shutil.copytree(src, dst)
                else:
                    shutil.copy2(src, dst)
        except Exception as e:
            QMessageBox.critical(self, "Paste Failed", str(e))

    # ── Path helpers ─────────────────────────────
    def _copy_path(self, path: str):
        from PyQt5.QtWidgets import QApplication
        QApplication.clipboard().setText(path)

    def _copy_rel_path(self, path: str):
        from PyQt5.QtWidgets import QApplication
        rel = os.path.relpath(path, self._root_path) if self._root_path else path
        QApplication.clipboard().setText(rel)

    def _reveal(self, path: str):
        try:
            target = path if os.path.isdir(path) else os.path.dirname(path)
            system = platform.system()
            if system == "Windows":
                subprocess.Popen(["explorer", os.path.normpath(target)])
            elif system == "Darwin":
                subprocess.Popen(["open", target])
            else:
                # Linux — try common file managers
                for fm in ("xdg-open", "nautilus", "thunar", "dolphin", "nemo"):
                    if shutil.which(fm):
                        subprocess.Popen([fm, target])
                        break
        except Exception as e:
            QMessageBox.warning(self, "Reveal Failed", str(e))

    # ═══════════════════════════════════════════
    # Click handlers
    # ═══════════════════════════════════════════
    def _on_click(self, proxy_index: QModelIndex):
        path = self._path_at(proxy_index)
        if path and os.path.isfile(path):
            self.file_opened.emit(path)

    def _on_double_click(self, proxy_index: QModelIndex):
        path = self._path_at(proxy_index)
        if path and os.path.isdir(path):
            if self.tree.isExpanded(proxy_index):
                self.tree.collapse(proxy_index)
            else:
                self.tree.expand(proxy_index)

    # ── Keyboard: Del → delete, F2 → rename ──────
    def keyPressEvent(self, event):
        indexes = self.tree.selectedIndexes()
        if event.key() == Qt.Key_Delete and indexes:
            paths = list({self._path_at(i) for i in indexes if self._path_at(i)})
            self._delete(paths)
            return
        if event.key() == Qt.Key_F2 and indexes:
            self._rename(indexes[0])
            return
        if event.matches(QKeySequence.Copy) and indexes:
            self._copy(self._path_at(indexes[0]))
            return
        if event.matches(QKeySequence.Cut) and indexes:
            self._cut(self._path_at(indexes[0]))
            return
        if event.matches(QKeySequence.Paste):
            target = self._selected_dir() or self._root_path
            self._paste(target)
            return
        super().keyPressEvent(event)

    # ═══════════════════════════════════════════
    # Helpers
    # ═══════════════════════════════════════════
    def _path_at(self, proxy_index: QModelIndex) -> str:
        if not proxy_index.isValid():
            return ""
        src = self._proxy.mapToSource(proxy_index)
        return self._fs.filePath(src)

    def _selected_dir(self) -> str:
        """Return the directory of the currently selected item."""
        indexes = self.tree.selectedIndexes()
        if not indexes:
            return self._root_path
        path = self._path_at(indexes[0])
        return path if os.path.isdir(path) else os.path.dirname(path)
