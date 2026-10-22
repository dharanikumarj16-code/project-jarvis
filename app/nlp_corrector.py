"""
app/nlp_corrector.py  –  Safe, Meaning-Preserving NLP Normalizer & Spell Corrector
==================================================================================

Applies lightweight, low-latency text normalization and spelling correction to
natural-language user commands while strictly protecting literal values
(filenames, extensions, paths, quoted strings, URLs, shell flags).
"""

import re
from typing import List, Tuple, Dict, Any


# Exact typo dictionary for Windows OS, desktop, filesystem, and voice transcription
KNOWN_TYPOS: Dict[str, str] = {
    # Actions & Verbs
    "opn": "open",
    "opne": "open",
    "openn": "open",
    "creat": "create",
    "craete": "create",
    "cteate": "create",
    "mak": "make",
    "chage": "change",
    "chnage": "change",
    "cahnge": "change",
    "renam": "rename",
    "renmae": "rename",
    "mov": "move",
    "moev": "move",
    "mvoe": "move",
    "delte": "delete",
    "delet": "delete",
    "dlete": "delete",
    "delt": "delete",
    "recycel": "recycle",
    "recyce": "recycle",
    "restor": "restore",
    "restoer": "restore",
    "clik": "click",
    "clck": "click",
    "cilck": "click",
    "rigt": "right",
    "rigth": "right",
    "dwn": "down",
    "dowwn": "down",
    "serch": "search",
    "serach": "search",
    "saerch": "search",
    "sreach": "search",
    "scrn": "screen",
    "captur": "capture",
    "termnal": "terminal",
    "temrinal": "terminal",
    "trminal": "terminal",
    "opration": "operation",
    "opertion": "operation",
    "operaton": "operation",
    "duplicat": "duplicate",
    "duplcate": "duplicate",
    "duplciate": "duplicate",
    # Objects & Nouns
    "exploer": "explorer",
    "explrer": "explorer",
    "exporer": "explorer",
    "foler": "folder",
    "floder": "folder",
    "foder": "folder",
    "foldr": "folder",
    "fil": "file",
    "fiel": "file",
    "fiile": "file",
    "nme": "name",
    "naem": "name",
    "drictory": "directory",
    "directry": "directory",
    "direcotry": "directory",
    "dirctory": "directory",
    "documnts": "documents",
    "documets": "documents",
    "docments": "documents",
    "dcouments": "documents",
    "dowloads": "downloads",
    "downlods": "downloads",
    "downlaods": "downloads",
    "projcts": "projects",
    "projekts": "projects",
    "prjcts": "projects",
    "desktp": "desktop",
    "desktopp": "desktop",
    "picturs": "pictures",
    # Applications & Web
    "chrme": "chrome",
    "chorme": "chrome",
    "crom": "chrome",
    "notepd": "notepad",
    "notpad": "notepad",
    "notepadd": "notepad",
    "edg": "edge",
    "calcultor": "calculator",
    "calclator": "calculator",
    "gooogle": "google",
    "gogle": "google",
    "googel": "google",
    "broswer": "browser",
    "brower": "browser",
    "borwser": "browser",
}

# Protected canonical token vocabulary for bounded Levenshtein correction
CANONICAL_VOCABULARY = {
    "open", "close", "start", "launch", "exit", "quit", "create", "make",
    "list", "show", "read", "write", "run", "exec", "check",
    "folder", "folders", "directory", "directories", "file", "files", "name", "rename", "change", "move", "copy",
    "delete", "recycle", "restore", "undo", "operation", "search", "find",
    "explorer", "terminal", "command", "click", "double", "right", "scroll",
    "down", "up", "type", "press", "enter", "volume", "mute", "screenshot",
    "capture", "duplicate", "downloads", "documents", "desktop", "chrome",
    "notepad", "edge", "calculator", "archive", "extract", "compare",
    "google", "browser", "window", "windows", "app", "apps", "button", "link", "box", "boxes", "icon", "icons", "text", "content", "area",
    "news", "song", "songs", "music", "media", "video", "videos", "track", "tracks",
    "whatsapp", "message", "messages", "contact", "contacts",
    "system", "info", "information", "cpu", "ram", "memory", "disk", "specs", "battery", "percentage",
    "process", "processes", "running", "task", "tasks", "status", "active", "foreground", "current",
    "named", "called", "into", "from", "with", "under", "this", "that", "last", "first", "all", "new", "old", "items", "test",
}


def _levenshtein_distance(s1: str, s2: str) -> int:
    """Compute standard Levenshtein edit distance between two strings."""
    if len(s1) < len(s2):
        return _levenshtein_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)

    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row

    return previous_row[-1]


class LightweightTextCorrector:
    """Fast, deterministic normalizer with literal isolation and typo correction."""

    # Regex patterns identifying literal values that MUST NOT be spell-checked
    LITERAL_PATTERNS = [
        # 1. Quoted text: "something" or 'something'
        r'([\'"][^\'"]+[\'"])',
        # 2. Windows drive paths: C:\folder\file.txt
        r'(\b[a-zA-Z]:[\\/][^\s]+)',
        # 3. Relative paths: ./folder/file or ..\file
        r'(\b(?:\.\/|\.\\|\.\.\/|\.\.\\)[^\s]+)',
        # 4. URLs: http:// or https:// or www.
        r'(\b(?:https?://|www\.)[^\s]+)',
        # 5. Files with extensions: e.g. report.pdf, teh.py, data.json, app.exe
        r'(\b[a-zA-Z0-9_\-]+\.[a-zA-Z0-9]{1,6}\b)',
        # 6. Explicitly named entity following 'named' or 'called' (e.g. "named teh.py")
        r'(?<=\bnamed\s)([a-zA-Z0-9_\-\.]+)',
        r'(?<=\bcalled\s)([a-zA-Z0-9_\-\.]+)',
        # 7. Shell flags: -rf, --verbose
        r'(\s-[a-zA-Z]+\b|\s--[a-zA-Z\-]+\b)',
    ]

    def extract_literals(self, text: str) -> Tuple[str, List[str]]:
        """Isolate literal tokens (filenames, paths, quotes) and replace with placeholders."""
        literals: List[str] = []
        masked_text = text

        for pattern in self.LITERAL_PATTERNS:
            matches = list(re.finditer(pattern, masked_text, flags=re.IGNORECASE))
            # Process in reverse to maintain string index offsets
            for m in reversed(matches):
                val = m.group(0).strip()
                if not val or val.startswith("__LIT_"):
                    continue
                placeholder = f"__LIT_{len(literals)}__"
                literals.append(val)
                start, end = m.span()
                masked_text = masked_text[:start] + placeholder + masked_text[end:]

        return masked_text, literals

    def restore_literals(self, text: str, literals: List[str]) -> str:
        """Replace placeholders with the original untouched literal values."""
        restored = text
        for idx, val in enumerate(literals):
            placeholder = f"__LIT_{idx}__"
            restored = restored.replace(placeholder, val)
        return restored

    def correct_word(self, word: str) -> str:
        """Correct a single word if it is a known typo or close to canonical vocabulary."""
        lower = word.lower().strip()
        if lower.startswith("__lit_"):
            return word  # Preserve literal placeholder

        # 0. Already a canonical word
        if lower in CANONICAL_VOCABULARY:
            return word

        # 1. Exact typo dictionary lookup (O(1))
        if lower in KNOWN_TYPOS:
            return KNOWN_TYPOS[lower]

        # 2. Repeated characters collapse (e.g. 'cooppy' -> 'copy', 'opennd' -> 'open')
        collapsed = re.sub(r'(.)\1{2,}', r'\1', lower)
        if collapsed in KNOWN_TYPOS:
            return KNOWN_TYPOS[collapsed]
        if collapsed in CANONICAL_VOCABULARY:
            return collapsed

        # 3. Fuzzy Levenshtein match for words >= 4 chars with distance == 1
        if len(lower) >= 4 and not any(c.isdigit() for c in lower):
            for candidate in CANONICAL_VOCABULARY:
                if abs(len(candidate) - len(lower)) <= 1:
                    if _levenshtein_distance(lower, candidate) == 1:
                        return candidate

        return word

    def normalize(self, user_input: str) -> Tuple[str, str, List[str]]:
        """Normalize and spell-correct user input while keeping literal data intact.

        Returns: (normalized_text, masked_template, extracted_literals)
        """
        raw = user_input.strip()
        if not raw:
            return "", "", []

        # 1. Extract and protect literals
        masked, literals = self.extract_literals(raw)

        # 2. Normalize whitespace and clean punctuation (except inside placeholders)
        # Protect placeholders from punctuation stripping
        tokens = masked.split()
        corrected_tokens: List[str] = []

        for token in tokens:
            if token.startswith("__LIT_"):
                corrected_tokens.append(token)
                continue

            # Strip outer punctuation for correction
            match = re.match(r"^([^\w]*)([\w\-]+)([^\w]*)$", token)
            if match:
                prefix, core, suffix = match.groups()
                corrected_core = self.correct_word(core)
                corrected_tokens.append(f"{prefix}{corrected_core}{suffix}")
            else:
                corrected_tokens.append(token)

        corrected_masked = " ".join(corrected_tokens)

        # 3. Restore literals exactly
        final_normalized = self.restore_literals(corrected_masked, literals)

        return final_normalized, corrected_masked, literals


# Global singleton normalizer
nlp_corrector = LightweightTextCorrector()
