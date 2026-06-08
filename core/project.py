"""
core/project.py — Project configuration manager (.shield_config.json)

Each project folder can have a .shield_config.json with:
{
    "python_path": "/usr/bin/python3",
    "run_args": [],
    "env": { "MY_VAR": "value" },
    "entry_point": "main.py",
    "exclude_dirs": [".git", "__pycache__", "node_modules"],
    "language": "python",
    "name": "My Project"
}
"""

import os
import json
import shutil
from typing import Optional

CONFIG_FILE = ".shield_config.json"

DEFAULTS = {
    "python_path": "",          # empty = auto-detect
    "run_args": [],
    "env": {},
    "entry_point": "",
    "exclude_dirs": [".git", "__pycache__", "node_modules", ".venv", "venv", ".idea"],
    "language": "python",
    "name": "",
    "tab_size": 4,
    "word_wrap": False,
    "font_size": 12,
}


class ProjectConfig:
    def __init__(self, folder: str):
        self.folder = folder
        self.config_path = os.path.join(folder, CONFIG_FILE)
        self._data = dict(DEFAULTS)
        self.load()

    # ── Load / Save ──────────────────────────────
    def load(self):
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                self._data.update(saved)
            except Exception:
                pass  # corrupted config → use defaults
        # Auto-fill name from folder
        if not self._data["name"]:
            self._data["name"] = os.path.basename(self.folder)

    def save(self):
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2)
            return True
        except Exception as e:
            return False

    # ── Property access ──────────────────────────
    def get(self, key, default=None):
        return self._data.get(key, default)

    def set(self, key, value):
        self._data[key] = value

    def to_dict(self):
        return dict(self._data)

    # ── Python interpreter resolution ────────────
    def resolve_python(self) -> str:
        """Return the best Python executable for this project."""
        configured = self._data.get("python_path", "")
        if configured and os.path.isfile(configured):
            return configured

        # Check for venv inside project
        for venv_name in (".venv", "venv", "env"):
            for bin_dir in ("bin", "Scripts"):
                for py_name in ("python3", "python"):
                    candidate = os.path.join(self.folder, venv_name, bin_dir, py_name)
                    if os.path.isfile(candidate):
                        return candidate

        # Fall back to system python
        return shutil.which("python3") or shutil.which("python") or "python"

    # ── Entry point resolution ───────────────────
    def resolve_entry(self, active_file: Optional[str] = None) -> Optional[str]:
        """Return the file to run: active_file > entry_point > None."""
        if active_file:
            return active_file
        ep = self._data.get("entry_point", "")
        if ep:
            full = os.path.join(self.folder, ep)
            if os.path.isfile(full):
                return full
        return None

    # ── Build env ────────────────────────────────
    def build_env(self) -> dict:
        """Merge system env with project overrides."""
        env = dict(os.environ)
        env.update(self._data.get("env", {}))
        return env

    # ── Run command builder ──────────────────────
    def build_run_command(self, file_path: str, language: str) -> list:
        """Return a command list suitable for subprocess."""
        extra_args = self._data.get("run_args", [])

        if language == "python":
            py = self.resolve_python()
            return [py, "-u", file_path] + extra_args

        elif language in ("javascript",):
            node = shutil.which("node") or "node"
            return [node, file_path] + extra_args

        elif language == "bash":
            bash = shutil.which("bash") or "bash"
            return [bash, file_path] + extra_args

        elif language == "c":
            # Try to compile then run
            out = file_path.replace(".c", "").replace(".cpp", "")
            compiler = shutil.which("g++") or shutil.which("gcc") or "gcc"
            return [compiler, file_path, "-o", out, "&&", out]

        return ["echo", f"[S.H.I.E.L.D.] Cannot run .{language} files directly"]

    def __repr__(self):
        return f"ProjectConfig(name={self._data['name']!r}, folder={self.folder!r})"


# ── Standalone helpers ────────────────────────────────────────────────────────
def load_or_create(folder: str) -> ProjectConfig:
    return ProjectConfig(folder)


def config_exists(folder: str) -> bool:
    return os.path.exists(os.path.join(folder, CONFIG_FILE))
