"""
core/highlighter.py — Multi-language syntax highlighter for S.H.I.E.L.D. IDE
Supports: Python, JavaScript, Bash, C/C++, JSON, Markdown
"""

from PyQt5.QtGui import QSyntaxHighlighter, QTextCharFormat, QColor, QFont
from PyQt5.QtCore import QRegularExpression


# ──────────────────────────────────────────────
# Color palette (shared across all grammars)
# ──────────────────────────────────────────────
COLORS = {
    "keyword":   "#00FFFF",
    "string":    "#ffaa00",
    "comment":   "#55ff55",
    "number":    "#ff66ff",
    "function":  "#ffdd88",
    "class_":    "#00ff66",
    "decorator": "#ff55ff",
    "type":      "#88ccff",
    "operator":  "#ff8844",
    "builtin":   "#aaddff",
    "variable":  "#dddddd",
    "heading":   "#00ffff",
    "bold":      "#ffaa00",
    "italic":    "#aaffcc",
    "constant":  "#ff9966",
}


def _fmt(color, bold=False, italic=False):
    f = QTextCharFormat()
    f.setForeground(QColor(color))
    if bold:
        f.setFontWeight(QFont.Bold)
    if italic:
        f.setFontItalic(True)
    return f


# ──────────────────────────────────────────────
# Grammar definitions
# ──────────────────────────────────────────────
GRAMMARS = {
    "python": {
        "keywords": [
            'def', 'class', 'if', 'else', 'elif', 'while', 'for', 'try', 'except',
            'finally', 'import', 'from', 'as', 'return', 'break', 'continue', 'with',
            'lambda', 'pass', 'yield', 'True', 'False', 'None', 'and', 'or', 'not',
            'in', 'is', 'raise', 'assert', 'del', 'global', 'nonlocal', 'async', 'await'
        ],
        "builtins": [
            'print', 'len', 'range', 'type', 'int', 'str', 'float', 'list', 'dict',
            'set', 'tuple', 'bool', 'open', 'enumerate', 'zip', 'map', 'filter',
            'sorted', 'reversed', 'sum', 'min', 'max', 'abs', 'round', 'isinstance',
            'hasattr', 'getattr', 'setattr', 'super', 'property', 'staticmethod',
            'classmethod', 'input', 'repr', 'id', 'hash', 'dir', 'vars', 'help',
        ],
        "string_patterns": [
            r'"""[\s\S]*?"""',
            r"'''[\s\S]*?'''",
            r'"[^"\\]*(\\.[^"\\]*)*"',
            r"'[^'\\]*(\\.[^'\\]*)*'",
        ],
        "comment_char": "#",
        "extras": [
            (r'\bdef\s+(\w+)\b',   "function", 1),
            (r'\bclass\s+(\w+)\b', "class_",   1),
            (r'@\w+',              "decorator", 0),
            (r'\b(\w+)\s*(?=\()',  "function",  1),
        ],
    },
    "javascript": {
        "keywords": [
            'const', 'let', 'var', 'function', 'return', 'if', 'else', 'for', 'while',
            'do', 'switch', 'case', 'break', 'continue', 'class', 'extends', 'new',
            'this', 'super', 'import', 'export', 'default', 'from', 'async', 'await',
            'try', 'catch', 'finally', 'throw', 'typeof', 'instanceof', 'in', 'of',
            'true', 'false', 'null', 'undefined', 'void', 'delete', 'yield',
        ],
        "builtins": [
            'console', 'Math', 'JSON', 'Object', 'Array', 'String', 'Number', 'Boolean',
            'Promise', 'setTimeout', 'setInterval', 'clearTimeout', 'clearInterval',
            'fetch', 'document', 'window', 'navigator', 'localStorage', 'sessionStorage',
        ],
        "string_patterns": [
            r'`[^`\\]*(\\.[^`\\]*)*`',
            r'"[^"\\]*(\\.[^"\\]*)*"',
            r"'[^'\\]*(\\.[^'\\]*)*'",
        ],
        "comment_char": "//",
        "extras": [
            (r'\bfunction\s+(\w+)\b', "function", 1),
            (r'\bclass\s+(\w+)\b',   "class_",   1),
            (r'\b(\w+)\s*(?=\()',     "function",  1),
            (r'=>',                   "operator",  0),
        ],
    },
    "bash": {
        "keywords": [
            'if', 'then', 'else', 'elif', 'fi', 'for', 'do', 'done', 'while',
            'until', 'case', 'esac', 'function', 'return', 'exit', 'in',
            'echo', 'export', 'source', 'local', 'readonly', 'shift',
        ],
        "builtins": [
            'cd', 'ls', 'pwd', 'mkdir', 'rm', 'cp', 'mv', 'cat', 'grep',
            'sed', 'awk', 'find', 'chmod', 'chown', 'sudo', 'apt', 'pip',
            'git', 'curl', 'wget', 'tar', 'zip', 'unzip', 'ssh', 'scp',
        ],
        "string_patterns": [
            r'"[^"\\]*(\\.[^"\\]*)*"',
            r"'[^'\\]*(\\.[^'\\]*)*'",
        ],
        "comment_char": "#",
        "extras": [
            (r'\$\w+',     "variable", 0),
            (r'\$\{[^}]+\}', "variable", 0),
        ],
    },
    "c": {
        "keywords": [
            'int', 'float', 'double', 'char', 'void', 'bool', 'long', 'short',
            'unsigned', 'signed', 'struct', 'union', 'enum', 'typedef', 'const',
            'static', 'extern', 'auto', 'register', 'if', 'else', 'for', 'while',
            'do', 'switch', 'case', 'break', 'continue', 'return', 'goto', 'default',
            'sizeof', 'include', 'define', 'ifdef', 'ifndef', 'endif', 'pragma',
            'nullptr', 'true', 'false', 'class', 'public', 'private', 'protected',
            'new', 'delete', 'virtual', 'override', 'namespace', 'using', 'template',
        ],
        "builtins": [
            'printf', 'scanf', 'malloc', 'free', 'calloc', 'realloc',
            'strlen', 'strcpy', 'strcat', 'strcmp', 'memset', 'memcpy',
            'cout', 'cin', 'endl', 'std',
        ],
        "string_patterns": [
            r'"[^"\\]*(\\.[^"\\]*)*"',
            r"'[^'\\]*(\\.[^'\\]*)*'",
            r'#\s*include\s*[<"][^>"]+[>"]',
        ],
        "comment_char": "//",
        "extras": [
            (r'/\*[\s\S]*?\*/', "comment", 0),
            (r'#\w+',           "type",    0),
        ],
    },
    "json": {
        "keywords": ['true', 'false', 'null'],
        "builtins": [],
        "string_patterns": [r'"[^"\\]*(\\.[^"\\]*)*"'],
        "comment_char": None,
        "extras": [],
    },
    "markdown": {
        "keywords": [],
        "builtins": [],
        "string_patterns": [r'`[^`]+`'],
        "comment_char": None,
        "extras": [
            (r'^#{1,6}\s.*',      "heading",  0),
            (r'\*\*[^*]+\*\*',    "bold",     0),
            (r'\*[^*]+\*',        "italic",   0),
            (r'!\[[^\]]*\]\([^)]*\)', "function", 0),
            (r'\[[^\]]*\]\([^)]*\)',  "type",     0),
        ],
    },
}

EXTENSION_MAP = {
    ".py":   "python",
    ".js":   "javascript",
    ".ts":   "javascript",
    ".jsx":  "javascript",
    ".tsx":  "javascript",
    ".sh":   "bash",
    ".bash": "bash",
    ".zsh":  "bash",
    ".c":    "c",
    ".cpp":  "c",
    ".cc":   "c",
    ".h":    "c",
    ".hpp":  "c",
    ".json": "json",
    ".md":   "markdown",
    ".txt":  "python",   # fallback
}


def detect_language(path: str) -> str:
    import os
    _, ext = os.path.splitext(path or "")
    return EXTENSION_MAP.get(ext.lower(), "python")


# ──────────────────────────────────────────────
# Universal Highlighter
# ──────────────────────────────────────────────
class UniversalHighlighter(QSyntaxHighlighter):
    def __init__(self, document, language="python"):
        super().__init__(document)
        self.set_language(language)

    def set_language(self, language: str):
        self.language = language
        self.grammar = GRAMMARS.get(language, GRAMMARS["python"])
        self.rehighlight()

    def highlightBlock(self, text):
        g = self.grammar

        # Keywords
        kw_fmt = _fmt(COLORS["keyword"], bold=True)
        for word in g["keywords"]:
            exp = QRegularExpression(r'\b' + word + r'\b')
            it = exp.globalMatch(text)
            while it.hasNext():
                m = it.next()
                self.setFormat(m.capturedStart(), m.capturedLength(), kw_fmt)

        # Builtins
        bi_fmt = _fmt(COLORS["builtin"])
        for word in g["builtins"]:
            exp = QRegularExpression(r'\b' + word + r'\b')
            it = exp.globalMatch(text)
            while it.hasNext():
                m = it.next()
                self.setFormat(m.capturedStart(), m.capturedLength(), bi_fmt)

        # Strings
        for pattern in g["string_patterns"]:
            exp = QRegularExpression(pattern)
            it = exp.globalMatch(text)
            while it.hasNext():
                m = it.next()
                self.setFormat(m.capturedStart(), m.capturedLength(), _fmt(COLORS["string"]))

        # Inline comment
        if g["comment_char"]:
            idx = text.find(g["comment_char"])
            if idx != -1:
                # Don't highlight comment inside a string
                self.setFormat(idx, len(text) - idx, _fmt(COLORS["comment"]))

        # Numbers
        num_exp = QRegularExpression(r'\b\d+(\.\d+)?\b')
        it = num_exp.globalMatch(text)
        while it.hasNext():
            m = it.next()
            self.setFormat(m.capturedStart(), m.capturedLength(), _fmt(COLORS["number"]))

        # Extras (language-specific patterns)
        for pattern, color_key, group in g["extras"]:
            exp = QRegularExpression(pattern)
            it = exp.globalMatch(text)
            while it.hasNext():
                m = it.next()
                start = m.capturedStart(group)
                length = m.capturedLength(group)
                if start >= 0 and length > 0:
                    self.setFormat(start, length, _fmt(COLORS[color_key]))
