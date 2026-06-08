# S.H.I.E.L.D. IDE v3.0 — Transparent HUD Edition

> **S**ynthetic **H**UD **I**ntelligent **E**ditor for **L**ive **D**evelopment

A frameless, translucent Python IDE built with PyQt5.

---

## Setup

```bash
pip install PyQt5 psutil
pip install anthropic   # optional — for AI Assistant panel
python main.py
```

---

## Project Structure

```
shield_ide/
├── main.py                  ← Entry point / main window
├── requirements.txt
├── core/
│   ├── highlighter.py       ← UniversalHighlighter (6 languages)
│   ├── editor.py            ← EditorTab + CodeEditor (line nums, find/replace)
│   └── project.py           ← ProjectConfig (.shield_config.json)
└── ui/
    ├── console.py           ← ConsoleWidget (ANSI, stdin, kill, scroll lock)
    ├── statusbar.py         ← StatusBar (git branch, CPU/RAM, cursor, time)
    ├── project_dialog.py    ← Project Settings dialog
    └── ai_panel.py          ← AI Assistant panel (Claude API)
```

---

## Features

### Editor
| Feature | Details |
|---|---|
| Multi-language syntax highlighting | Python, JavaScript/TypeScript, Bash, C/C++, JSON, Markdown |
| Line numbers | Gutter with current-line highlight |
| Auto-indent | Preserves indentation; extra indent after `:` |
| Smart backspace | Removes 4-space indent blocks |
| Find & Replace | Ctrl+H · regex support · case-sensitive toggle · Replace All |
| Multi-tab | Ctrl+Tab / Ctrl+Shift+Tab to cycle · dirty indicator (●) |
| Unsaved-changes guard | Prompts Save / Discard / Cancel on close |

### Running Code
| Shortcut | Action |
|---|---|
| Ctrl+R | Run current file/buffer |
| Ctrl+Shift+R | Clear console then run |
| F5 | Run project entry point |
| Shift+Enter | Run (from editor) |
| Ctrl+Enter | Clear + run (from editor) |
| Ctrl+K | Kill running process |

### Console
- ANSI color codes rendered as HTML
- stdin input bar (send input to running process)
- Scroll lock toggle
- Kill button

### Project Config (`.shield_config.json`)
```json
{
  "name": "My Project",
  "python_path": "/home/user/.venv/bin/python3",
  "entry_point": "main.py",
  "run_args": ["--debug"],
  "env": { "DEBUG": "1" },
  "exclude_dirs": [".git", "__pycache__", "node_modules"],
  "font_size": 12,
  "tab_size": 4,
  "word_wrap": false
}
```
Open via **Project → Project Settings…** (`Ctrl+,`)

### Status Bar
- ⎇ Git branch + dirty indicator (● when uncommitted changes)
- CPU % / RAM % with color thresholds
- Cursor position (Ln / Col)
- Language icon
- Clock

### AI Assistant Panel
- Toggle with `Ctrl+Shift+A`
- Modes: Explain · Debug · Refactor · Docs · Chat
- Sends current editor code as context
- Streams responses via Claude API
- Requires: `pip install anthropic`

### File Explorer
- Filters excluded dirs (configurable per project)
- Click any file to open in a new tab

---

## Keyboard Shortcuts

| Shortcut | Action |
|---|---|
| Ctrl+N | New file |
| Ctrl+O | Open file |
| Ctrl+Shift+O | Open folder |
| Ctrl+S | Save |
| Ctrl+Shift+S | Save As |
| Ctrl+W | Close tab |
| Ctrl+H | Find & Replace |
| F3 | Find next |
| Ctrl+R | Run |
| Ctrl+Shift+R | Run + Clear |
| F5 | Run entry point |
| Ctrl+K | Kill process |
| Ctrl+L | Clear console |
| Ctrl+B | Toggle Explorer |
| Ctrl+Shift+A | Toggle AI panel |
| Ctrl+\` | Toggle Console |
| Ctrl+Tab | Next tab |
| Ctrl+Shift+Tab | Previous tab |
| F11 | Toggle maximize |
| Alt+F4 | Exit |
