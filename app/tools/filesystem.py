"""
app/tools/filesystem.py  -  Enterprise Native Filesystem & File Explorer Tools for JARVIS OS
=============================================================================================

Comprehensive Windows filesystem operations, File Explorer shell integrations,
content inspection, batch management, archive handling, safe recycle bin deletion,
atomic writes, and verifiable operation undo/recovery.
"""

import os
import sys
import shutil
import hashlib
import json
import time
import datetime
from pathlib import Path
import ctypes
from ctypes import wintypes
import tempfile
import zipfile
import difflib
import re
import subprocess
import uuid
from typing import Dict, Any, List, Optional, Union, Tuple

from app.permissions import check_permission, PermissionLevel
from app.events import event_bus


# ============================================================================
# Operation Log & Undo Management
# ============================================================================

class FileOperationLog:
    """Thread-safe persistent log of file operations for auditing and undo recovery."""

    def __init__(self, log_dir: Optional[str] = None):
        if log_dir is None:
            log_dir = os.path.join(tempfile.gettempdir(), "jarvis_fs_ops")
        self.log_dir = Path(log_dir)
        self.backup_dir = self.log_dir / "backups"
        self.history_file = self.log_dir / "operations.json"
        self._ensure_dirs()
        self._history: List[Dict[str, Any]] = self._load_history()

    def _ensure_dirs(self) -> None:
        try:
            self.log_dir.mkdir(parents=True, exist_ok=True)
            self.backup_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass

    def _load_history(self) -> List[Dict[str, Any]]:
        if self.history_file.exists():
            try:
                data = json.loads(self.history_file.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    return data
            except Exception:
                pass
        return []

    def _save_history(self) -> None:
        try:
            # Keep latest 200 operations
            trimmed = self._history[-200:]
            self.history_file.write_text(json.dumps(trimmed, indent=2), encoding="utf-8")
        except Exception:
            pass

    def record(
        self,
        op_type: str,
        source: str,
        destination: Optional[str] = None,
        backup_path: Optional[str] = None,
        status: str = "success",
        error: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        op_id = f"op_{int(time.time())}_{uuid.uuid4().hex[:6]}"
        entry = {
            "operation_id": op_id,
            "type": op_type,
            "source": str(source),
            "destination": str(destination) if destination else None,
            "backup_path": str(backup_path) if backup_path else None,
            "timestamp": time.time(),
            "timestamp_iso": datetime.datetime.now().isoformat(),
            "status": status,
            "error": error,
            "undone": False,
            "metadata": metadata or {}
        }
        self._history.append(entry)
        self._save_history()
        return op_id

    def get_last_undoable_operation(self) -> Optional[Dict[str, Any]]:
        for op in reversed(self._history):
            if op.get("status") == "success" and not op.get("undone", False):
                if op.get("type") in ("rename", "move", "copy", "edit", "write_backup", "create_file"):
                    return op
        return None

    def get_operation(self, op_id: str) -> Optional[Dict[str, Any]]:
        for op in self._history:
            if op.get("operation_id") == op_id:
                return op
        return None

    def mark_undone(self, op_id: str) -> None:
        for op in self._history:
            if op.get("operation_id") == op_id:
                op["undone"] = True
                self._save_history()
                break

    def create_backup(self, file_path: Union[str, Path]) -> Optional[str]:
        p = Path(file_path).resolve()
        if not p.is_file():
            return None
        try:
            b_name = f"{p.stem}_{int(time.time())}_{uuid.uuid4().hex[:6]}{p.suffix}.bak"
            target = self.backup_dir / b_name
            shutil.copy2(str(p), str(target))
            return str(target)
        except Exception:
            return None


op_logger = FileOperationLog()


# ============================================================================
# Helpers & Windows Path Utilities
# ============================================================================

def _normalize_path(path: Union[str, Path]) -> Path:
    """Normalize Windows paths, resolve relative paths against current working directory."""
    raw = str(path).strip().strip('"').strip("'")
    if not raw:
        return Path.cwd()
    # Expand user environment variables and ~ home directory
    expanded = os.path.expanduser(os.path.expandvars(raw))
    return Path(expanded).resolve()


def _format_size(size_bytes: int) -> str:
    """Format bytes into readable string (B, KB, MB, GB, TB)."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    for unit in ["KB", "MB", "GB", "TB"]:
        size_bytes /= 1024.0
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
    return f"{size_bytes:.2f} PB"


# ============================================================================
# Category A: Discovery and Inspection
# ============================================================================

def get_current_directory() -> Dict[str, Any]:
    """Get the current working directory."""
    if not check_permission("get_current_directory", PermissionLevel.READ, {}):
        return {"success": False, "error": "Permission denied"}
    try:
        cwd = Path.cwd()
        return {"success": True, "path": str(cwd), "name": cwd.name}
    except Exception as e:
        return {"success": False, "error": str(e)}


def change_directory(path: str) -> Dict[str, Any]:
    """Change the active process working directory with validation."""
    if not check_permission("change_directory", PermissionLevel.ACTION, {"path": path}):
        return {"success": False, "error": "Permission denied"}
    try:
        target = _normalize_path(path)
        if not target.exists():
            return {"success": False, "error": f"Target directory does not exist: '{path}'"}
        if not target.is_dir():
            return {"success": False, "error": f"Path is not a directory: '{path}'"}
        os.chdir(str(target))
        return {
            "success": True,
            "message": f"Changed working directory to '{target}'",
            "cwd": str(target)
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def list_directory(
    path: str = ".",
    recursive: bool = False,
    max_depth: int = 1,
    show_hidden: bool = False,
    sort_by: str = "name",
    limit: int = 100
) -> Dict[str, Any]:
    """List files and subdirectories with structured file metadata and size."""
    if not check_permission("list_directory", PermissionLevel.READ, {"path": path}):
        return {"success": False, "error": "Permission denied"}
    try:
        p = _normalize_path(path)
        if not p.exists():
            return {"success": False, "error": f"Path '{path}' does not exist."}
        if not p.is_dir():
            return {"success": False, "error": f"Path '{path}' is not a directory."}

        entries: List[Dict[str, Any]] = []

        def _scan(current: Path, depth: int):
            if depth > max_depth:
                return
            try:
                for item in current.iterdir():
                    # Check hidden flag on Windows
                    is_hidden = False
                    try:
                        if item.name.startswith("."):
                            is_hidden = True
                        else:
                            attrs = ctypes.windll.kernel32.GetFileAttributesW(str(item))
                            if attrs != -1 and (attrs & 2):  # FILE_ATTRIBUTE_HIDDEN
                                is_hidden = True
                    except Exception:
                        pass

                    if is_hidden and not show_hidden:
                        continue

                    # Avoid following junctions/symlinks recursively
                    is_sym = item.is_symlink()
                    is_d = item.is_dir() and not is_sym

                    stat = None
                    try:
                        stat = item.stat()
                        size = stat.st_size if not is_d else None
                        mtime = datetime.datetime.fromtimestamp(stat.st_mtime).isoformat()
                        ctime = datetime.datetime.fromtimestamp(stat.st_ctime).isoformat()
                    except Exception:
                        size = None
                        mtime = None
                        ctime = None

                    entries.append({
                        "name": item.name,
                        "path": str(item),
                        "is_dir": is_d,
                        "is_symlink": is_sym,
                        "extension": item.suffix.lower() if not is_d else "",
                        "size_bytes": size,
                        "size_formatted": _format_size(size) if size is not None else None,
                        "modified": mtime,
                        "created": ctime,
                        "is_hidden": is_hidden
                    })

                    if recursive and is_d and depth < max_depth:
                        _scan(item, depth + 1)
            except PermissionError:
                pass

        _scan(p, 1)

        # Sorting
        if sort_by == "size":
            entries.sort(key=lambda x: (x["size_bytes"] or 0), reverse=True)
        elif sort_by == "date":
            entries.sort(key=lambda x: (x["modified"] or ""), reverse=True)
        else:
            entries.sort(key=lambda x: (not x["is_dir"], x["name"].lower()))

        total_found = len(entries)
        returned_entries = entries[:limit]

        out_lines = [f"Directory: {str(p)} ({total_found} items)"]
        if not returned_entries:
            out_lines.append("  (empty directory)")
        else:
            for item in returned_entries:
                if item["is_dir"]:
                    out_lines.append(f"  📁 [DIR]  {item['name']}")
                else:
                    sz = item.get("size_formatted") or ""
                    out_lines.append(f"  📄 [FILE] {item['name']:<35} {sz:>10}")
            if total_found > len(returned_entries):
                out_lines.append(f"  ... ({total_found - len(returned_entries)} more items)")
        formatted_output = "\n".join(out_lines)

        return {
            "success": True,
            "path": str(p),
            "total_count": total_found,
            "returned_count": min(total_found, limit),
            "entries": returned_entries,
            "output": formatted_output,
            "message": formatted_output
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def search_files(
    query: str,
    root_dir: str = ".",
    recursive: bool = True,
    max_results: int = 50
) -> Dict[str, Any]:
    """Search for files matching substring or wildcard pattern in filename."""
    if not check_permission("search_files", PermissionLevel.READ, {"query": query, "root_dir": root_dir}):
        return {"success": False, "error": "Permission denied"}
    try:
        base = _normalize_path(root_dir)
        if not base.exists() or not base.is_dir():
            return {"success": False, "error": f"Root directory '{root_dir}' does not exist."}

        matches: List[Dict[str, Any]] = []
        pattern = query if ("*" in query or "?" in query) else f"*{query}*"

        iterator = base.rglob(pattern) if recursive else base.glob(pattern)
        for p in iterator:
            try:
                # Do not follow junctions/symlinks outside base
                stat = p.stat()
                matches.append({
                    "name": p.name,
                    "path": str(p),
                    "is_dir": p.is_dir(),
                    "size_bytes": stat.st_size if p.is_file() else None,
                    "size_formatted": _format_size(stat.st_size) if p.is_file() else None,
                    "modified": datetime.datetime.fromtimestamp(stat.st_mtime).isoformat()
                })
                if len(matches) >= max_results:
                    break
            except Exception:
                continue

        return {
            "success": True,
            "query": query,
            "root_dir": str(base),
            "total_matches": len(matches),
            "matches": matches
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def search_file_contents(
    query: str,
    root_dir: str = ".",
    file_pattern: str = "*.*",
    case_sensitive: bool = False,
    max_results: int = 30
) -> Dict[str, Any]:
    """Search for text string inside files under root_dir."""
    if not check_permission("search_file_contents", PermissionLevel.READ, {"query": query, "root_dir": root_dir}):
        return {"success": False, "error": "Permission denied"}
    try:
        base = _normalize_path(root_dir)
        if not base.exists() or not base.is_dir():
            return {"success": False, "error": f"Root directory '{root_dir}' does not exist."}

        target_query = query if case_sensitive else query.lower()
        results: List[Dict[str, Any]] = []

        for p in base.rglob(file_pattern):
            if not p.is_file():
                continue
            # Skip very large files (> 20 MB)
            try:
                if p.stat().st_size > 20 * 1024 * 1024:
                    continue
                with open(p, "r", encoding="utf-8", errors="ignore") as f:
                    for line_idx, line in enumerate(f, start=1):
                        comp_line = line if case_sensitive else line.lower()
                        if target_query in comp_line:
                            results.append({
                                "file": str(p),
                                "line_number": line_idx,
                                "line_content": line.strip()[:200]
                            })
                            if len(results) >= max_results:
                                return {"success": True, "query": query, "results": results}
            except Exception:
                continue

        return {"success": True, "query": query, "results": results}
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_file_info(path: str) -> Dict[str, Any]:
    """Get comprehensive metadata, timestamps, permissions, and hashes for a path."""
    if not check_permission("get_file_info", PermissionLevel.READ, {"path": path}):
        return {"success": False, "error": "Permission denied"}
    try:
        p = _normalize_path(path)
        if not p.exists():
            return {"success": False, "error": f"Path '{path}' does not exist."}

        stat = p.stat()
        is_file = p.is_file()
        is_dir = p.is_dir()

        size_bytes = stat.st_size if is_file else None
        if is_dir:
            # Quick shallow sum of direct contents
            try:
                size_bytes = sum(f.stat().st_size for f in p.rglob("*") if f.is_file())
            except Exception:
                size_bytes = None

        return {
            "success": True,
            "path": str(p),
            "name": p.name,
            "parent": str(p.parent),
            "is_file": is_file,
            "is_dir": is_dir,
            "is_symlink": p.is_symlink(),
            "extension": p.suffix.lower() if is_file else "",
            "size_bytes": size_bytes,
            "size_formatted": _format_size(size_bytes) if size_bytes is not None else None,
            "created": datetime.datetime.fromtimestamp(stat.st_ctime).isoformat(),
            "modified": datetime.datetime.fromtimestamp(stat.st_mtime).isoformat(),
            "accessed": datetime.datetime.fromtimestamp(stat.st_atime).isoformat(),
            "readonly": not (stat.st_mode & 0o200),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_directory_tree(
    path: str = ".",
    max_depth: int = 3,
    show_files: bool = True,
    max_entries: int = 150
) -> Dict[str, Any]:
    """Generate a formatted visual directory hierarchy tree."""
    if not check_permission("get_directory_tree", PermissionLevel.READ, {"path": path}):
        return {"success": False, "error": "Permission denied"}
    try:
        base = _normalize_path(path)
        if not base.exists() or not base.is_dir():
            return {"success": False, "error": f"Directory '{path}' does not exist."}

        lines: List[str] = [base.name + "/"]
        entry_count = 0

        def _build_tree(dir_path: Path, prefix: str, depth: int):
            nonlocal entry_count
            if depth > max_depth or entry_count >= max_entries:
                return

            try:
                items = sorted(list(dir_path.iterdir()), key=lambda x: (not x.is_dir(), x.name.lower()))
            except PermissionError:
                lines.append(f"{prefix}└── [Permission Denied]")
                return

            # Filter items
            if not show_files:
                items = [i for i in items if i.is_dir()]

            count = len(items)
            for idx, item in enumerate(items):
                if entry_count >= max_entries:
                    lines.append(f"{prefix}... (truncated after {max_entries} entries)")
                    return

                entry_count += 1
                is_last = (idx == count - 1)
                connector = "└── " if is_last else "├── "
                sub_prefix = "    " if is_last else "│   "

                if item.is_dir() and not item.is_symlink():
                    lines.append(f"{prefix}{connector}{item.name}/")
                    _build_tree(item, prefix + sub_prefix, depth + 1)
                elif show_files and item.is_file():
                    lines.append(f"{prefix}{connector}{item.name}")

        _build_tree(base, "", 1)
        tree_text = "\n".join(lines)
        return {
            "success": True,
            "root": str(base),
            "entry_count": entry_count,
            "tree": tree_text
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def find_recent_files(root_dir: str = ".", hours: int = 24, max_results: int = 30) -> Dict[str, Any]:
    """Find files modified within the last N hours."""
    if not check_permission("find_recent_files", PermissionLevel.READ, {"root_dir": root_dir, "hours": hours}):
        return {"success": False, "error": "Permission denied"}
    try:
        base = _normalize_path(root_dir)
        threshold = time.time() - (hours * 3600)
        recent = []

        for p in base.rglob("*"):
            if not p.is_file():
                continue
            try:
                mtime = p.stat().st_mtime
                if mtime >= threshold:
                    recent.append({
                        "name": p.name,
                        "path": str(p),
                        "size_bytes": p.stat().st_size,
                        "modified": datetime.datetime.fromtimestamp(mtime).isoformat()
                    })
                    if len(recent) >= max_results:
                        break
            except Exception:
                continue

        recent.sort(key=lambda x: x["modified"], reverse=True)
        return {"success": True, "hours": hours, "count": len(recent), "files": recent}
    except Exception as e:
        return {"success": False, "error": str(e)}


def find_large_files(root_dir: str = ".", min_size_mb: float = 50.0, max_results: int = 30) -> Dict[str, Any]:
    """Find files larger than a given size in megabytes."""
    if not check_permission("find_large_files", PermissionLevel.READ, {"root_dir": root_dir, "min_size_mb": min_size_mb}):
        return {"success": False, "error": "Permission denied"}
    try:
        base = _normalize_path(root_dir)
        threshold_bytes = int(min_size_mb * 1024 * 1024)
        large_files = []

        for p in base.rglob("*"):
            if not p.is_file():
                continue
            try:
                size = p.stat().st_size
                if size >= threshold_bytes:
                    large_files.append({
                        "name": p.name,
                        "path": str(p),
                        "size_bytes": size,
                        "size_formatted": _format_size(size),
                        "modified": datetime.datetime.fromtimestamp(p.stat().st_mtime).isoformat()
                    })
                    if len(large_files) >= max_results:
                        break
            except Exception:
                continue

        large_files.sort(key=lambda x: x["size_bytes"], reverse=True)
        return {"success": True, "min_size_mb": min_size_mb, "count": len(large_files), "files": large_files}
    except Exception as e:
        return {"success": False, "error": str(e)}


def find_empty_directories(root_dir: str = ".", max_results: int = 50) -> Dict[str, Any]:
    """Identify directories containing zero files or subfolders."""
    if not check_permission("find_empty_directories", PermissionLevel.READ, {"root_dir": root_dir}):
        return {"success": False, "error": "Permission denied"}
    try:
        base = _normalize_path(root_dir)
        empty_dirs = []

        for p in base.rglob("*"):
            if not p.is_dir() or p.is_symlink():
                continue
            try:
                if not any(p.iterdir()):
                    empty_dirs.append(str(p))
                    if len(empty_dirs) >= max_results:
                        break
            except Exception:
                continue

        return {"success": True, "count": len(empty_dirs), "empty_directories": empty_dirs}
    except Exception as e:
        return {"success": False, "error": str(e)}


def find_duplicate_files(
    root_dir: str = ".",
    min_size_bytes: int = 1024,
    max_results: int = 30
) -> Dict[str, Any]:
    """Identify duplicate files based on size matching followed by MD5/SHA256 hash checks."""
    if not check_permission("find_duplicate_files", PermissionLevel.READ, {"root_dir": root_dir}):
        return {"success": False, "error": "Permission denied"}
    try:
        base = _normalize_path(root_dir)
        size_map: Dict[int, List[Path]] = {}

        # 1. Bucket by size
        for p in base.rglob("*"):
            if not p.is_file() or p.is_symlink():
                continue
            try:
                sz = p.stat().st_size
                if sz >= min_size_bytes:
                    size_map.setdefault(sz, []).append(p)
            except Exception:
                continue

        duplicates: List[Dict[str, Any]] = []
        # 2. Hash only collision buckets
        for sz, path_list in size_map.items():
            if len(path_list) < 2:
                continue

            hash_map: Dict[str, List[str]] = {}
            for p in path_list:
                try:
                    h = hashlib.md5(p.read_bytes()[:65536]).hexdigest()
                    hash_map.setdefault(h, []).append(str(p))
                except Exception:
                    continue

            for h, paths in hash_map.items():
                if len(paths) >= 2:
                    duplicates.append({
                        "size_bytes": sz,
                        "size_formatted": _format_size(sz),
                        "hash": h,
                        "paths": paths
                    })
                    if len(duplicates) >= max_results:
                        return {"success": True, "duplicates": duplicates}

        return {"success": True, "count": len(duplicates), "duplicates": duplicates}
    except Exception as e:
        return {"success": False, "error": str(e)}


def compare_files(path1: str, path2: str, mode: str = "diff") -> Dict[str, Any]:
    """Compare two files by hash or line-by-line unified diff."""
    if not check_permission("compare_files", PermissionLevel.READ, {"path1": path1, "path2": path2}):
        return {"success": False, "error": "Permission denied"}
    try:
        p1 = _normalize_path(path1)
        p2 = _normalize_path(path2)

        if not p1.is_file() or not p2.is_file():
            return {"success": False, "error": "Both target paths must exist and be regular files."}

        h1 = hashlib.sha256(p1.read_bytes()).hexdigest()
        h2 = hashlib.sha256(p2.read_bytes()).hexdigest()
        identical = (h1 == h2)

        diff_lines = []
        if not identical and mode == "diff":
            try:
                t1 = p1.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
                t2 = p2.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
                diff = difflib.unified_diff(t1, t2, fromfile=str(p1), tofile=str(p2), n=3)
                diff_lines = list(diff)[:100]  # Cap diff display
            except Exception:
                diff_lines = ["Binary or un-decodable files differ."]

        return {
            "success": True,
            "identical": identical,
            "file1": {"path": str(p1), "sha256": h1, "size": p1.stat().st_size},
            "file2": {"path": str(p2), "sha256": h2, "size": p2.stat().st_size},
            "diff": "".join(diff_lines) if diff_lines else None
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def compare_directories(dir1: str, dir2: str) -> Dict[str, Any]:
    """Compare contents of two directories (files only in dir1, dir2, common, modified)."""
    if not check_permission("compare_directories", PermissionLevel.READ, {"dir1": dir1, "dir2": dir2}):
        return {"success": False, "error": "Permission denied"}
    try:
        d1 = _normalize_path(dir1)
        d2 = _normalize_path(dir2)

        if not d1.is_dir() or not d2.is_dir():
            return {"success": False, "error": "Both paths must be existing directories."}

        files1 = {str(p.relative_to(d1)): p for p in d1.rglob("*") if p.is_file()}
        files2 = {str(p.relative_to(d2)): p for p in d2.rglob("*") if p.is_file()}

        set1 = set(files1.keys())
        set2 = set(files2.keys())

        only_in_1 = list(set1 - set2)
        only_in_2 = list(set2 - set1)
        common = set1.intersection(set2)

        modified = []
        for rel in common:
            f1 = files1[rel]
            f2 = files2[rel]
            if f1.stat().st_size != f2.stat().st_size or hashlib.md5(f1.read_bytes()).digest() != hashlib.md5(f2.read_bytes()).digest():
                modified.append(rel)

        return {
            "success": True,
            "dir1": str(d1),
            "dir2": str(d2),
            "only_in_dir1": sorted(only_in_1)[:50],
            "only_in_dir2": sorted(only_in_2)[:50],
            "modified_in_both": sorted(modified)[:50],
            "identical_count": len(common) - len(modified)
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def check_path_exists(path: str) -> Dict[str, Any]:
    """Check whether a path exists and report whether it is a file, folder, or symlink."""
    if not check_permission("check_path_exists", PermissionLevel.READ, {"path": path}):
        return {"success": False, "error": "Permission denied"}
    try:
        p = _normalize_path(path)
        exists = p.exists()
        return {
            "success": True,
            "path": str(p),
            "exists": exists,
            "is_file": p.is_file() if exists else False,
            "is_dir": p.is_dir() if exists else False,
            "is_symlink": p.is_symlink() if exists else False
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def inspect_file_permissions(path: str) -> Dict[str, Any]:
    """Inspect read/write/execute permissions and Windows attributes for a target path."""
    if not check_permission("inspect_file_permissions", PermissionLevel.READ, {"path": path}):
        return {"success": False, "error": "Permission denied"}
    try:
        p = _normalize_path(path)
        if not p.exists():
            return {"success": False, "error": f"Path '{path}' does not exist."}

        return {
            "success": True,
            "path": str(p),
            "readable": os.access(p, os.R_OK),
            "writable": os.access(p, os.W_OK),
            "executable": os.access(p, os.X_OK)
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


# ============================================================================
# Category B: File and Folder Creation
# ============================================================================

def create_file(path: str, content: str = "", overwrite: bool = False) -> Dict[str, Any]:
    """Create a new file with optional initial content."""
    if not check_permission("create_file", PermissionLevel.ACTION, {"path": path, "overwrite": overwrite}):
        return {"success": False, "error": "Permission denied"}
    try:
        p = _normalize_path(path)
        if p.exists() and not overwrite:
            return {
                "success": False,
                "error": f"File '{path}' already exists. Pass overwrite=True to allow replacement."
            }

        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")

        # Verify
        if not p.exists() or p.stat().st_size != len(content.encode("utf-8")):
            return {"success": False, "error": "Post-creation verification failed."}

        op_id = op_logger.record("create_file", str(p), metadata={"size": len(content)})
        return {
            "success": True,
            "path": str(p),
            "bytes_written": len(content.encode("utf-8")),
            "operation_id": op_id
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def create_directory(path: str) -> Dict[str, Any]:
    """Create a directory (and any parent directories)."""
    if not check_permission("create_directory", PermissionLevel.ACTION, {"path": path}):
        return {"success": False, "error": "Permission denied"}
    try:
        p = _normalize_path(path)
        if p.exists():
            if p.is_dir():
                return {"success": True, "path": str(p), "message": "Directory already exists."}
            return {"success": False, "error": f"Path '{path}' already exists as a non-directory."}

        p.mkdir(parents=True, exist_ok=True)
        op_id = op_logger.record("create_dir", str(p))
        return {
            "success": True,
            "path": str(p),
            "message": "Directory created successfully.",
            "operation_id": op_id
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def create_directory_tree(base_path: str, subdirectories: List[str]) -> Dict[str, Any]:
    """Create multiple directory structures under a base path in a single validated operation."""
    if not check_permission("create_directory_tree", PermissionLevel.ACTION, {"base_path": base_path}):
        return {"success": False, "error": "Permission denied"}
    try:
        base = _normalize_path(base_path)
        base.mkdir(parents=True, exist_ok=True)

        created = []
        for sub in subdirectories:
            target = base / sub
            target.mkdir(parents=True, exist_ok=True)
            created.append(str(target))

        return {
            "success": True,
            "base_path": str(base),
            "created_count": len(created),
            "directories": created
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def create_project_structure(base_path: str, structure: Dict[str, Any]) -> Dict[str, Any]:
    """Create a complete nested project directory and files structure."""
    if not check_permission("create_project_structure", PermissionLevel.ACTION, {"base_path": base_path}):
        return {"success": False, "error": "Permission denied"}
    try:
        base = _normalize_path(base_path)
        base.mkdir(parents=True, exist_ok=True)

        created_files = []
        created_dirs = []

        def _traverse(curr_dir: Path, nodes: Dict[str, Any]):
            for name, val in nodes.items():
                target = curr_dir / name
                if isinstance(val, dict):
                    target.mkdir(parents=True, exist_ok=True)
                    created_dirs.append(str(target))
                    _traverse(target, val)
                elif isinstance(val, str):
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text(val, encoding="utf-8")
                    created_files.append(str(target))
                elif val is None:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.touch()
                    created_files.append(str(target))

        _traverse(base, structure)
        return {
            "success": True,
            "base_path": str(base),
            "directories_created": len(created_dirs),
            "files_created": len(created_files)
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def create_shortcut(target_path: str, shortcut_path: str, description: str = "") -> Dict[str, Any]:
    """Create a Windows .lnk shortcut pointing to a target file or folder via PowerShell."""
    if not check_permission("create_shortcut", PermissionLevel.ACTION, {"target": target_path, "shortcut": shortcut_path}):
        return {"success": False, "error": "Permission denied"}
    try:
        tgt = _normalize_path(target_path)
        lnk = _normalize_path(shortcut_path)
        if not str(lnk).lower().endswith(".lnk"):
            lnk = Path(str(lnk) + ".lnk")

        if not tgt.exists():
            return {"success": False, "error": f"Shortcut target does not exist: '{target_path}'"}

        lnk.parent.mkdir(parents=True, exist_ok=True)
        ps_cmd = (
            f'$ws = New-Object -ComObject WScript.Shell; '
            f'$s = $ws.CreateShortcut("{lnk}"); '
            f'$s.TargetPath = "{tgt}"; '
            f'$s.Description = "{description}"; '
            f'$s.Save()'
        )
        res = subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True, text=True, timeout=10)
        if res.returncode == 0 and lnk.exists():
            return {"success": True, "shortcut": str(lnk), "target": str(tgt)}
        return {"success": False, "error": res.stderr.strip() or "Failed to create shortcut"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def create_temporary_file(prefix: str = "jarvis_", suffix: str = ".tmp", content: str = "") -> Dict[str, Any]:
    """Create a managed temporary file."""
    if not check_permission("create_temporary_file", PermissionLevel.LOW_RISK, {}):
        return {"success": False, "error": "Permission denied"}
    try:
        fd, temp_path = tempfile.mkstemp(prefix=prefix, suffix=suffix)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        return {"success": True, "path": temp_path, "bytes_written": len(content.encode("utf-8"))}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ============================================================================
# Category C: Rename, Copy, and Move
# ============================================================================

def rename_path(source: str, new_name_or_path: str, overwrite: bool = False) -> Dict[str, Any]:
    """Rename a file or folder safely with post-verification."""
    if not check_permission("rename_path", PermissionLevel.ACTION, {"source": source, "new": new_name_or_path}):
        return {"success": False, "error": "Permission denied"}
    try:
        src = _normalize_path(source)
        if not src.exists():
            return {"success": False, "error": f"Source path '{source}' does not exist."}

        # If new_name_or_path is just a filename, place in same parent directory
        if os.path.sep not in new_name_or_path and "/" not in new_name_or_path:
            dst = src.parent / new_name_or_path
        else:
            dst = _normalize_path(new_name_or_path)

        if dst.exists() and not overwrite:
            return {"success": False, "error": f"Destination '{dst}' already exists. Pass overwrite=True to allow replacement."}

        shutil.move(str(src), str(dst))

        # Verification
        if not dst.exists() or src.exists():
            return {"success": False, "error": "Rename verification failed: State did not update."}

        op_id = op_logger.record("rename", str(src), str(dst))
        return {
            "success": True,
            "old_path": str(src),
            "new_path": str(dst),
            "operation_id": op_id
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def copy_file(source: str, destination: str, overwrite: bool = False) -> Dict[str, Any]:
    """Copy a file to a new location preserving metadata."""
    if not check_permission("copy_file", PermissionLevel.ACTION, {"source": source, "destination": destination}):
        return {"success": False, "error": "Permission denied"}
    try:
        src = _normalize_path(source)
        dst = _normalize_path(destination)

        if not src.is_file():
            return {"success": False, "error": f"Source file '{source}' does not exist or is not a file."}

        if dst.is_dir():
            dst = dst / src.name

        if dst.exists() and not overwrite:
            return {"success": False, "error": f"Destination '{dst}' already exists. Set overwrite=True to replace."}

        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(src), str(dst))

        if not dst.exists() or dst.stat().st_size != src.stat().st_size:
            return {"success": False, "error": "Copy verification failed: Destination file size mismatch."}

        op_id = op_logger.record("copy", str(src), str(dst))
        return {
            "success": True,
            "source": str(src),
            "destination": str(dst),
            "bytes_copied": dst.stat().st_size,
            "operation_id": op_id
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def copy_directory(source: str, destination: str, overwrite: bool = False) -> Dict[str, Any]:
    """Recursively copy an entire directory structure."""
    if not check_permission("copy_directory", PermissionLevel.ACTION, {"source": source, "destination": destination}):
        return {"success": False, "error": "Permission denied"}
    try:
        src = _normalize_path(source)
        dst = _normalize_path(destination)

        if not src.is_dir():
            return {"success": False, "error": f"Source directory '{source}' does not exist or is not a directory."}

        # Prevent copying a directory into itself
        if dst.resolve().is_relative_to(src.resolve()):
            return {"success": False, "error": "Cannot copy a directory inside itself."}

        if dst.exists() and not overwrite:
            return {"success": False, "error": f"Destination directory '{dst}' already exists."}

        shutil.copytree(str(src), str(dst), dirs_exist_ok=overwrite)

        if not dst.exists():
            return {"success": False, "error": "Directory copy verification failed."}

        op_id = op_logger.record("copy_dir", str(src), str(dst))
        return {"success": True, "source": str(src), "destination": str(dst), "operation_id": op_id}
    except Exception as e:
        return {"success": False, "error": str(e)}


def move_file(source: str, destination: str, overwrite: bool = False) -> Dict[str, Any]:
    """Move a file to a new directory or filename (supports cross-drive movement)."""
    if not check_permission("move_file", PermissionLevel.ACTION, {"source": source, "destination": destination}):
        return {"success": False, "error": "Permission denied"}
    try:
        src = _normalize_path(source)
        dst = _normalize_path(destination)

        if not src.is_file():
            return {"success": False, "error": f"Source file '{source}' does not exist."}

        if dst.is_dir():
            dst = dst / src.name

        if dst.exists() and not overwrite:
            return {"success": False, "error": f"Destination '{dst}' already exists."}

        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))

        if not dst.exists() or src.exists():
            return {"success": False, "error": "Move verification failed: Destination does not exist or source remains."}

        op_id = op_logger.record("move", str(src), str(dst))
        return {"success": True, "source": str(src), "destination": str(dst), "operation_id": op_id}
    except Exception as e:
        return {"success": False, "error": str(e)}


def move_directory(source: str, destination: str, overwrite: bool = False) -> Dict[str, Any]:
    """Move an entire directory tree."""
    if not check_permission("move_directory", PermissionLevel.ACTION, {"source": source, "destination": destination}):
        return {"success": False, "error": "Permission denied"}
    try:
        src = _normalize_path(source)
        dst = _normalize_path(destination)

        if not src.is_dir():
            return {"success": False, "error": f"Source directory '{source}' does not exist."}

        if dst.resolve().is_relative_to(src.resolve()):
            return {"success": False, "error": "Cannot move a directory into its own subdirectory."}

        if dst.exists() and not overwrite:
            return {"success": False, "error": f"Destination '{dst}' already exists."}

        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))

        op_id = op_logger.record("move_dir", str(src), str(dst))
        return {"success": True, "source": str(src), "destination": str(dst), "operation_id": op_id}
    except Exception as e:
        return {"success": False, "error": str(e)}


def duplicate_file(source: str, new_name: Optional[str] = None) -> Dict[str, Any]:
    """Create a copy of a file in the same directory with a 'copy' suffix or custom name."""
    if not check_permission("duplicate_file", PermissionLevel.ACTION, {"source": source}):
        return {"success": False, "error": "Permission denied"}
    try:
        src = _normalize_path(source)
        if not src.is_file():
            return {"success": False, "error": f"Source file '{source}' does not exist."}

        if new_name:
            dst = src.parent / new_name
        else:
            dst = src.parent / f"{src.stem} - Copy{src.suffix}"
            idx = 2
            while dst.exists():
                dst = src.parent / f"{src.stem} - Copy ({idx}){src.suffix}"
                idx += 1

        shutil.copy2(str(src), str(dst))
        op_id = op_logger.record("copy", str(src), str(dst))
        return {"success": True, "source": str(src), "duplicate": str(dst), "operation_id": op_id}
    except Exception as e:
        return {"success": False, "error": str(e)}


def batch_rename(directory: str, pattern: str, replacement: str, dry_run: bool = False) -> Dict[str, Any]:
    """Batch rename files in a folder matching a regex or substring pattern."""
    if not check_permission("batch_rename", PermissionLevel.ACTION, {"directory": directory, "pattern": pattern}):
        return {"success": False, "error": "Permission denied"}
    try:
        d = _normalize_path(directory)
        if not d.is_dir():
            return {"success": False, "error": f"Directory '{directory}' does not exist."}

        planned = []
        for item in d.iterdir():
            if re.search(pattern, item.name):
                new_name = re.sub(pattern, replacement, item.name)
                target = d / new_name
                planned.append({"source": str(item), "destination": str(target)})

        if dry_run:
            return {"success": True, "dry_run": True, "planned_renames": planned}

        renamed = []
        for plan in planned:
            try:
                shutil.move(plan["source"], plan["destination"])
                renamed.append(plan)
            except Exception:
                pass

        return {"success": True, "count": len(renamed), "renamed": renamed}
    except Exception as e:
        return {"success": False, "error": str(e)}


def batch_copy(source_paths: List[str], destination_dir: str, overwrite: bool = False) -> Dict[str, Any]:
    """Copy multiple files or folders into a target directory."""
    if not check_permission("batch_copy", PermissionLevel.ACTION, {"count": len(source_paths), "destination": destination_dir}):
        return {"success": False, "error": "Permission denied"}
    try:
        dst_dir = _normalize_path(destination_dir)
        dst_dir.mkdir(parents=True, exist_ok=True)

        copied = []
        failed = []

        for p_str in source_paths:
            try:
                src = _normalize_path(p_str)
                if not src.exists():
                    failed.append({"source": p_str, "error": "Source path not found"})
                    continue

                target = dst_dir / src.name
                if target.exists() and not overwrite:
                    failed.append({"source": p_str, "error": "Destination already exists"})
                    continue

                if src.is_file():
                    shutil.copy2(str(src), str(target))
                else:
                    shutil.copytree(str(src), str(target), dirs_exist_ok=overwrite)

                copied.append(str(target))
            except Exception as e:
                failed.append({"source": p_str, "error": str(e)})

        return {
            "success": len(copied) > 0,
            "copied_count": len(copied),
            "failed_count": len(failed),
            "copied": copied,
            "failed": failed
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def batch_move(source_paths: List[str], destination_dir: str, overwrite: bool = False) -> Dict[str, Any]:
    """Move multiple files or folders into a target destination directory."""
    if not check_permission("batch_move", PermissionLevel.ACTION, {"count": len(source_paths), "destination": destination_dir}):
        return {"success": False, "error": "Permission denied"}
    try:
        dst_dir = _normalize_path(destination_dir)
        dst_dir.mkdir(parents=True, exist_ok=True)

        moved = []
        failed = []

        for p_str in source_paths:
            try:
                src = _normalize_path(p_str)
                if not src.exists():
                    failed.append({"source": p_str, "error": "Source does not exist"})
                    continue

                target = dst_dir / src.name
                if target.exists() and not overwrite:
                    failed.append({"source": p_str, "error": "Destination already exists"})
                    continue

                shutil.move(str(src), str(target))
                moved.append(str(target))
            except Exception as e:
                failed.append({"source": p_str, "error": str(e)})

        return {
            "success": len(moved) > 0,
            "moved_count": len(moved),
            "failed_count": len(failed),
            "moved": moved,
            "failed": failed
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


# ============================================================================
# Category D: Delete and Recovery (Recycle Bin & Safe Undo)
# ============================================================================

def move_to_recycle_bin(path: str) -> Dict[str, Any]:
    """Send a file or folder safely to the Windows Recycle Bin so it can be restored."""
    if not check_permission("move_to_recycle_bin", PermissionLevel.LOW_RISK, {"path": path}):
        return {"success": False, "error": "Permission denied"}
    try:
        p = _normalize_path(path)
        if not p.exists():
            return {"success": False, "error": f"Path '{path}' does not exist."}

        full_path = str(p)

        # 1. Native Windows Shell API: SHFileOperationW with FOF_ALLOWUNDO
        try:
            class SHFILEOPSTRUCTW(ctypes.Structure):
                _fields_ = [
                    ("hwnd", wintypes.HWND),
                    ("wFunc", wintypes.UINT),
                    ("pFrom", wintypes.LPCWSTR),
                    ("pTo", wintypes.LPCWSTR),
                    ("fFlags", wintypes.WORD),
                    ("fAnyOperationsAborted", wintypes.BOOL),
                    ("hNameMappings", wintypes.LPVOID),
                    ("lpszProgressTitle", wintypes.LPCWSTR),
                ]

            FO_DELETE = 0x0003
            FOF_ALLOWUNDO = 0x0040
            FOF_NOCONFIRMATION = 0x0010
            FOF_SILENT = 0x0004
            FOF_NOERRORUI = 0x0400

            # Double null-terminated string required by Win32 API
            double_null_path = full_path + "\0\0"
            file_op = SHFILEOPSTRUCTW()
            file_op.hwnd = 0
            file_op.wFunc = FO_DELETE
            file_op.pFrom = double_null_path
            file_op.pTo = None
            file_op.fFlags = FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_SILENT | FOF_NOERRORUI
            file_op.fAnyOperationsAborted = False
            file_op.hNameMappings = None
            file_op.lpszProgressTitle = None

            ret = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(file_op))
            if ret == 0 and not file_op.fAnyOperationsAborted and not p.exists():
                op_id = op_logger.record("recycle", full_path)
                return {
                    "success": True,
                    "recycled": True,
                    "path": full_path,
                    "message": f"Successfully moved '{p.name}' to the Windows Recycle Bin.",
                    "operation_id": op_id
                }
        except Exception:
            pass

        # 2. Robust PowerShell fallback via Microsoft.VisualBasic.FileIO.FileSystem
        try:
            if p.is_file():
                ps_cmd = (
                    f'Add-Type -AssemblyName Microsoft.VisualBasic; '
                    f'[Microsoft.VisualBasic.FileIO.FileSystem]::DeleteFile("{full_path}", '
                    f'"OnlyErrorDialogs", "SendToRecycleBin")'
                )
            else:
                ps_cmd = (
                    f'Add-Type -AssemblyName Microsoft.VisualBasic; '
                    f'[Microsoft.VisualBasic.FileIO.FileSystem]::DeleteDirectory("{full_path}", '
                    f'"OnlyErrorDialogs", "SendToRecycleBin")'
                )
            res = subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True, text=True, timeout=15)
            if res.returncode == 0 and not p.exists():
                op_id = op_logger.record("recycle", full_path)
                return {
                    "success": True,
                    "recycled": True,
                    "path": full_path,
                    "message": f"Successfully moved '{p.name}' to the Windows Recycle Bin.",
                    "operation_id": op_id
                }
        except Exception:
            pass

        return {"success": False, "error": f"Failed to recycle path '{path}'."}
    except Exception as e:
        return {"success": False, "error": str(e)}


def inspect_recycle_bin(limit: int = 30) -> Dict[str, Any]:
    """Inspect contents of the Windows Recycle Bin."""
    if not check_permission("inspect_recycle_bin", PermissionLevel.READ, {}):
        return {"success": False, "error": "Permission denied"}
    try:
        ps_cmd = (
            '$shell = New-Object -ComObject Shell.Application; '
            '$bin = $shell.Namespace(0xA); '
            '$items = @(); '
            'foreach ($item in $bin.Items()) { '
            '  $items += [PSCustomObject]@{ '
            '    Name = $item.Name; '
            '    Path = $item.Path; '
            '    Size = $item.Size; '
            '    Type = $item.Type '
            '  } '
            '}; '
            '$items | ConvertTo-Json -Compress'
        )
        res = subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True, text=True, timeout=15)
        if res.returncode == 0 and res.stdout.strip():
            try:
                data = json.loads(res.stdout.strip())
                if isinstance(data, dict):
                    data = [data]
                return {"success": True, "count": len(data), "items": data[:limit]}
            except Exception:
                pass
        return {"success": True, "count": 0, "items": []}
    except Exception as e:
        return {"success": False, "error": str(e)}


def restore_from_recycle_bin(original_filename_or_path: str) -> Dict[str, Any]:
    """Restore an item from the Windows Recycle Bin by its original name or path."""
    if not check_permission("restore_from_recycle_bin", PermissionLevel.ACTION, {"target": original_filename_or_path}):
        return {"success": False, "error": "Permission denied"}
    try:
        target_name = os.path.basename(original_filename_or_path).lower()
        ps_cmd = (
            f'$shell = New-Object -ComObject Shell.Application; '
            f'$bin = $shell.Namespace(0xA); '
            f'$restored = $false; '
            f'foreach ($item in $bin.Items()) {{ '
            f'  if ($item.Name.ToLower() -eq "{target_name}") {{ '
            f'    $verbs = $item.Verbs(); '
            f'    foreach ($v in $verbs) {{ '
            f'      if ($v.Name -match "undelete|restore") {{ '
            f'        $v.DoIt(); '
            f'        $restored = $true; '
            f'        break; '
            f'      }} '
            f'    }} '
            f'  }} '
            f'  if ($restored) {{ break }} '
            f'}}; '
            f'Write-Output $restored'
        )
        res = subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True, text=True, timeout=20)
        success = "True" in res.stdout
        if success:
            return {"success": True, "message": f"Successfully restored '{target_name}' from the Recycle Bin."}
        return {"success": False, "error": f"Item '{original_filename_or_path}' was not found in Recycle Bin or could not be restored."}
    except Exception as e:
        return {"success": False, "error": str(e)}


def permanently_delete(path: str, recursive: bool = False, force: bool = False) -> Dict[str, Any]:
    """Permanently delete a file or directory (irreversible sensitive operation)."""
    if not check_permission("permanently_delete", PermissionLevel.DESTRUCTIVE, {"path": path, "recursive": recursive}):
        return {"success": False, "error": "Permission denied"}
    try:
        p = _normalize_path(path)
        if not p.exists():
            return {"success": False, "error": f"Path '{path}' does not exist."}

        # Prevent deleting system roots
        if str(p).lower() in ("c:\\", "d:\\", "c:/", "d:/", os.environ.get("SystemRoot", "").lower()):
            return {"success": False, "error": "Action rejected: Refusing to permanently delete system root directory."}

        if p.is_file():
            if force:
                os.chmod(p, 0o777)
            p.unlink()
        elif p.is_dir():
            if recursive:
                shutil.rmtree(str(p))
            else:
                p.rmdir()

        if p.exists():
            return {"success": False, "error": "Permanent deletion verification failed: Path still exists."}

        op_logger.record("permanent_delete", str(p))
        return {"success": True, "message": f"Permanently deleted '{path}'"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def delete_empty_directory(path: str) -> Dict[str, Any]:
    """Delete an empty directory."""
    if not check_permission("delete_empty_directory", PermissionLevel.ACTION, {"path": path}):
        return {"success": False, "error": "Permission denied"}
    try:
        p = _normalize_path(path)
        if not p.exists() or not p.is_dir():
            return {"success": False, "error": f"Path '{path}' is not an existing directory."}
        p.rmdir()
        return {"success": True, "message": f"Empty directory '{path}' removed successfully."}
    except OSError as e:
        return {"success": False, "error": f"Directory is not empty or cannot be removed: {e}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def undo_supported_file_operation(operation_id: Optional[str] = None) -> Dict[str, Any]:
    """Undo the last supported file operation (rename, move, copy, edit)."""
    if not check_permission("undo_supported_file_operation", PermissionLevel.ACTION, {"operation_id": operation_id}):
        return {"success": False, "error": "Permission denied"}
    try:
        op = None
        if operation_id:
            op = op_logger.get_operation(operation_id)
        else:
            op = op_logger.get_last_undoable_operation()

        if not op:
            return {"success": False, "error": "No undoable operation found."}

        op_type = op["type"]
        src = op["source"]
        dst = op.get("destination")
        backup = op.get("backup_path")

        # 1. Undo rename or move
        if op_type in ("rename", "move"):
            if not dst or not os.path.exists(dst):
                return {"success": False, "error": f"Cannot undo: Destination '{dst}' no longer exists."}
            shutil.move(dst, src)
            op_logger.mark_undone(op["operation_id"])
            return {"success": True, "message": f"Successfully reversed {op_type}: Moved '{dst}' back to '{src}'."}

        # 2. Undo copy
        elif op_type in ("copy", "copy_dir"):
            if not dst or not os.path.exists(dst):
                return {"success": False, "error": f"Created copy at '{dst}' does not exist."}
            if os.path.isfile(dst):
                os.remove(dst)
            else:
                shutil.rmtree(dst)
            op_logger.mark_undone(op["operation_id"])
            return {"success": True, "message": f"Successfully undone copy: Removed created duplicate '{dst}'."}

        # 3. Undo edit or write with backup
        elif op_type in ("edit", "write_backup") and backup and os.path.isfile(backup):
            shutil.copy2(backup, src)
            op_logger.mark_undone(op["operation_id"])
            return {"success": True, "message": f"Successfully restored original file content for '{src}'."}

        # 4. Undo newly created file
        elif op_type == "create_file" and os.path.isfile(src):
            os.remove(src)
            op_logger.mark_undone(op["operation_id"])
            return {"success": True, "message": f"Successfully undone file creation: Removed '{src}'."}

        return {"success": False, "error": f"Operation type '{op_type}' cannot be safely undone."}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ============================================================================
# Category E: File Content Operations
# ============================================================================

def read_text_file(
    path: str,
    offset: int = 0,
    limit: int = 1000,
    encoding: str = "utf-8"
) -> Dict[str, Any]:
    """Read lines of text from a file safely with line bounds and encoding fallback."""
    if not check_permission("read_text_file", PermissionLevel.READ, {"path": path}):
        return {"success": False, "error": "Permission denied"}
    try:
        p = _normalize_path(path)
        if not p.is_file():
            return {"success": False, "error": f"File '{path}' does not exist or is not a file."}

        # Handle encoding
        try:
            with open(p, "r", encoding=encoding, errors="replace") as f:
                lines = f.readlines()
        except Exception:
            with open(p, "r", encoding="latin-1", errors="replace") as f:
                lines = f.readlines()

        total_lines = len(lines)
        start = max(0, offset)
        end = min(total_lines, start + limit)
        slice_lines = lines[start:end]

        return {
            "success": True,
            "path": str(p),
            "total_lines": total_lines,
            "offset": start,
            "returned_lines": len(slice_lines),
            "content": "".join(slice_lines)
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def write_text_file(
    path: str,
    content: str,
    atomic: bool = True,
    create_backup: bool = False
) -> Dict[str, Any]:
    """Write text content to a file (atomic write with optional backup)."""
    if not check_permission("write_text_file", PermissionLevel.ACTION, {"path": path}):
        return {"success": False, "error": "Permission denied"}
    try:
        p = _normalize_path(path)
        p.parent.mkdir(parents=True, exist_ok=True)

        backup_path = None
        if create_backup and p.is_file():
            backup_path = op_logger.create_backup(p)

        encoded = content.encode("utf-8")

        if atomic:
            # Write to temporary file in same directory then atomic replace
            fd, temp_file = tempfile.mkstemp(dir=str(p.parent), prefix=".tmp_jarvis_")
            try:
                with os.fdopen(fd, "wb") as f:
                    f.write(encoded)
                os.replace(temp_file, str(p))
            except Exception:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
                raise
        else:
            p.write_bytes(encoded)

        # Verification
        if not p.exists() or p.stat().st_size != len(encoded):
            return {"success": False, "error": "Post-write verification failed: File size mismatch."}

        op_id = op_logger.record(
            "write_backup" if backup_path else "write",
            str(p),
            backup_path=backup_path,
            metadata={"size": len(encoded)}
        )
        return {
            "success": True,
            "path": str(p),
            "bytes_written": len(encoded),
            "backup_created": backup_path is not None,
            "operation_id": op_id
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def append_text_file(path: str, content: str) -> Dict[str, Any]:
    """Append text content to the end of a file."""
    if not check_permission("append_text_file", PermissionLevel.ACTION, {"path": path}):
        return {"success": False, "error": "Permission denied"}
    try:
        p = _normalize_path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        orig_size = p.stat().st_size if p.exists() else 0

        with open(p, "a", encoding="utf-8") as f:
            f.write(content)

        new_size = p.stat().st_size
        return {
            "success": True,
            "path": str(p),
            "bytes_appended": new_size - orig_size,
            "total_size": new_size
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def edit_text_file(
    path: str,
    line_start: int,
    line_end: int,
    replacement_text: str
) -> Dict[str, Any]:
    """Replace a specific 1-indexed line range in a text file with backup."""
    if not check_permission("edit_text_file", PermissionLevel.ACTION, {"path": path}):
        return {"success": False, "error": "Permission denied"}
    try:
        p = _normalize_path(path)
        if not p.is_file():
            return {"success": False, "error": f"File '{path}' does not exist."}

        backup_path = op_logger.create_backup(p)
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)

        start_idx = max(0, line_start - 1)
        end_idx = min(len(lines), line_end)

        rep = replacement_text if replacement_text.endswith("\n") else replacement_text + "\n"
        new_lines = lines[:start_idx] + [rep] + lines[end_idx:]

        p.write_text("".join(new_lines), encoding="utf-8")
        op_id = op_logger.record("edit", str(p), backup_path=backup_path)

        return {
            "success": True,
            "path": str(p),
            "lines_modified": end_idx - start_idx,
            "operation_id": op_id
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def replace_text(path: str, target: str, replacement: str, count: int = -1) -> Dict[str, Any]:
    """Replace occurrences of a substring inside a file."""
    if not check_permission("replace_text", PermissionLevel.ACTION, {"path": path}):
        return {"success": False, "error": "Permission denied"}
    try:
        p = _normalize_path(path)
        if not p.is_file():
            return {"success": False, "error": f"File '{path}' does not exist."}

        content = p.read_text(encoding="utf-8", errors="replace")
        occurrences = content.count(target)
        if occurrences == 0:
            return {"success": False, "error": f"Target substring not found in '{path}'."}

        backup_path = op_logger.create_backup(p)
        updated = content.replace(target, replacement, count) if count > 0 else content.replace(target, replacement)
        p.write_text(updated, encoding="utf-8")

        op_id = op_logger.record("edit", str(p), backup_path=backup_path)
        return {
            "success": True,
            "path": str(p),
            "replacements_made": occurrences if count < 0 else min(occurrences, count),
            "operation_id": op_id
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def read_json_file(path: str) -> Dict[str, Any]:
    """Read and parse a JSON file."""
    if not check_permission("read_json_file", PermissionLevel.READ, {"path": path}):
        return {"success": False, "error": "Permission denied"}
    try:
        p = _normalize_path(path)
        if not p.is_file():
            return {"success": False, "error": f"File '{path}' does not exist."}
        data = json.loads(p.read_text(encoding="utf-8"))
        return {"success": True, "path": str(p), "data": data}
    except Exception as e:
        return {"success": False, "error": str(e)}


def write_json_file(path: str, data: Any, indent: int = 2) -> Dict[str, Any]:
    """Serialize and atomically save data to a JSON file."""
    if not check_permission("write_json_file", PermissionLevel.ACTION, {"path": path}):
        return {"success": False, "error": "Permission denied"}
    try:
        serialized = json.dumps(data, indent=indent)
        return write_text_file(path, serialized, atomic=True)
    except Exception as e:
        return {"success": False, "error": str(e)}


def read_configuration_file(path: str) -> Dict[str, Any]:
    """Read a .env, .ini, .json, or key-value config file into a structured dictionary."""
    if not check_permission("read_configuration_file", PermissionLevel.READ, {"path": path}):
        return {"success": False, "error": "Permission denied"}
    try:
        p = _normalize_path(path)
        if not p.is_file():
            return {"success": False, "error": f"File '{path}' does not exist."}

        ext = p.suffix.lower()
        if ext == ".json":
            return {"success": True, "format": "json", "data": json.loads(p.read_text(encoding="utf-8"))}

        # Parse key-value / ini / env
        data = {}
        section = "DEFAULT"
        for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or line.startswith(";"):
                continue
            if line.startswith("[") and line.endswith("]"):
                section = line[1:-1]
                data.setdefault(section, {})
            elif "=" in line:
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip('"').strip("'")
                if section == "DEFAULT":
                    data[k] = v
                else:
                    data[section][k] = v

        return {"success": True, "format": ext or "env", "data": data}
    except Exception as e:
        return {"success": False, "error": str(e)}


def write_configuration_file(path: str, data: Dict[str, Any], format_type: str = "auto") -> Dict[str, Any]:
    """Write structured dictionary back to config or .env format."""
    if not check_permission("write_configuration_file", PermissionLevel.ACTION, {"path": path}):
        return {"success": False, "error": "Permission denied"}
    try:
        p = _normalize_path(path)
        fmt = p.suffix.lower() if format_type == "auto" else format_type

        if fmt == ".json" or fmt == "json":
            return write_json_file(path, data)

        lines = []
        for k, v in data.items():
            if isinstance(v, dict):
                lines.append(f"\n[{k}]")
                for sub_k, sub_v in v.items():
                    lines.append(f"{sub_k}={sub_v}")
            else:
                lines.append(f"{k}={v}")

        return write_text_file(path, "\n".join(lines) + "\n")
    except Exception as e:
        return {"success": False, "error": str(e)}


def inspect_source_file(path: str) -> Dict[str, Any]:
    """Inspect a Python or source code file: counts lines, extracts classes, functions, and docstrings."""
    if not check_permission("inspect_source_file", PermissionLevel.READ, {"path": path}):
        return {"success": False, "error": "Permission denied"}
    try:
        p = _normalize_path(path)
        if not p.is_file():
            return {"success": False, "error": f"File '{path}' does not exist."}

        text = p.read_text(encoding="utf-8", errors="replace")
        total_lines = len(text.splitlines())

        classes = []
        functions = []
        imports = []

        if p.suffix.lower() == ".py":
            import ast
            try:
                tree = ast.parse(text)
                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef):
                        classes.append(node.name)
                    elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        functions.append(node.name)
                    elif isinstance(node, ast.Import):
                        for n in node.names:
                            imports.append(n.name)
                    elif isinstance(node, ast.ImportFrom):
                        if node.module:
                            imports.append(node.module)
            except Exception:
                pass

        return {
            "success": True,
            "path": str(p),
            "total_lines": total_lines,
            "classes": sorted(list(set(classes))),
            "functions": sorted(list(set(functions))),
            "imports": sorted(list(set(imports)))
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def apply_approved_file_changes(changes: List[Dict[str, Any]], dry_run: bool = False) -> Dict[str, Any]:
    """Apply approved file modifications across multiple files atomically with tracking."""
    if not check_permission("apply_approved_file_changes", PermissionLevel.ACTION, {"count": len(changes)}):
        return {"success": False, "error": "Permission denied"}
    try:
        plan = []
        for change in changes:
            tgt = _normalize_path(change.get("path", ""))
            action = change.get("action", "write")
            content = change.get("content", "")
            plan.append({"target": str(tgt), "action": action, "size": len(content)})

        if dry_run:
            return {"success": True, "dry_run": True, "plan": plan}

        results = []
        for change in changes:
            tgt = change.get("path", "")
            content = change.get("content", "")
            res = write_text_file(tgt, content, atomic=True, create_backup=True)
            results.append({"path": tgt, "success": res.get("success", False)})

        return {"success": all(r["success"] for r in results), "results": results}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ============================================================================
# Category F: Archives and Metadata
# ============================================================================

def create_zip_archive(
    source_paths: List[str],
    archive_path: str,
    compression_level: int = 6
) -> Dict[str, Any]:
    """Create a ZIP archive from multiple files or directories with compression."""
    if not check_permission("create_zip_archive", PermissionLevel.ACTION, {"archive": archive_path}):
        return {"success": False, "error": "Permission denied"}
    try:
        arc = _normalize_path(archive_path)
        arc.parent.mkdir(parents=True, exist_ok=True)

        added_count = 0
        with zipfile.ZipFile(arc, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=compression_level) as zf:
            for s_str in source_paths:
                src = _normalize_path(s_str)
                if not src.exists():
                    continue
                if src.is_file():
                    zf.write(src, arcname=src.name)
                    added_count += 1
                elif src.is_dir():
                    for item in src.rglob("*"):
                        if item.is_file():
                            rel_name = os.path.relpath(item, src.parent)
                            zf.write(item, arcname=rel_name)
                            added_count += 1

        return {
            "success": True,
            "archive_path": str(arc),
            "files_added": added_count,
            "archive_size_bytes": arc.stat().st_size,
            "archive_size_formatted": _format_size(arc.stat().st_size)
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def extract_zip_archive(archive_path: str, destination_dir: str, overwrite: bool = False) -> Dict[str, Any]:
    """Extract a ZIP archive safely with path traversal protection (Anti-ZipSlip)."""
    if not check_permission("extract_zip_archive", PermissionLevel.ACTION, {"archive": archive_path, "destination": destination_dir}):
        return {"success": False, "error": "Permission denied"}
    try:
        arc = _normalize_path(archive_path)
        dst = _normalize_path(destination_dir)

        if not arc.is_file():
            return {"success": False, "error": f"Archive file '{archive_path}' does not exist."}

        dst.mkdir(parents=True, exist_ok=True)
        extracted = []

        with zipfile.ZipFile(arc, "r") as zf:
            for member in zf.infolist():
                # Prevent ZipSlip path traversal
                target_path = (dst / member.filename).resolve()
                if not target_path.is_relative_to(dst.resolve()):
                    return {"success": False, "error": f"Malicious path traversal detected in archive: '{member.filename}'"}

                if target_path.exists() and not overwrite and not member.is_dir():
                    continue

                zf.extract(member, dst)
                extracted.append(str(target_path))

        return {
            "success": True,
            "destination": str(dst),
            "files_extracted": len(extracted)
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def inspect_archive(archive_path: str) -> Dict[str, Any]:
    """Inspect contents, compressed sizes, and filenames of a ZIP archive."""
    if not check_permission("inspect_archive", PermissionLevel.READ, {"archive": archive_path}):
        return {"success": False, "error": "Permission denied"}
    try:
        arc = _normalize_path(archive_path)
        if not arc.is_file():
            return {"success": False, "error": f"Archive file '{archive_path}' does not exist."}

        entries = []
        with zipfile.ZipFile(arc, "r") as zf:
            for info in zf.infolist():
                entries.append({
                    "filename": info.filename,
                    "is_dir": info.is_dir(),
                    "file_size": info.file_size,
                    "compress_size": info.compress_size
                })

        return {
            "success": True,
            "archive": str(arc),
            "total_entries": len(entries),
            "entries": entries[:100]
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def calculate_file_hash(path: str, algorithm: str = "sha256") -> Dict[str, Any]:
    """Calculate cryptographic hash of a file (sha256, md5, sha1)."""
    if not check_permission("calculate_file_hash", PermissionLevel.READ, {"path": path}):
        return {"success": False, "error": "Permission denied"}
    try:
        p = _normalize_path(path)
        if not p.is_file():
            return {"success": False, "error": f"File '{path}' does not exist."}

        hasher = getattr(hashlib, algorithm.lower())()
        with open(p, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                hasher.update(chunk)

        digest = hasher.hexdigest()
        return {"success": True, "path": str(p), "algorithm": algorithm.upper(), "hash": digest}
    except Exception as e:
        return {"success": False, "error": str(e)}


def compare_file_hashes(path1: str, path2: str, algorithm: str = "sha256") -> Dict[str, Any]:
    """Compare two files via hash."""
    res1 = calculate_file_hash(path1, algorithm)
    res2 = calculate_file_hash(path2, algorithm)
    if not res1["success"]:
        return res1
    if not res2["success"]:
        return res2
    return {
        "success": True,
        "match": res1["hash"] == res2["hash"],
        "hash1": res1["hash"],
        "hash2": res2["hash"],
        "algorithm": algorithm.upper()
    }


def inspect_file_attributes(path: str) -> Dict[str, Any]:
    """Inspect Windows file attributes (hidden, readonly, archive, system)."""
    if not check_permission("inspect_file_attributes", PermissionLevel.READ, {"path": path}):
        return {"success": False, "error": "Permission denied"}
    try:
        p = _normalize_path(path)
        if not p.exists():
            return {"success": False, "error": f"Path '{path}' does not exist."}

        attrs = ctypes.windll.kernel32.GetFileAttributesW(str(p))
        if attrs == -1:
            return {"success": False, "error": "Failed to retrieve Windows file attributes"}

        return {
            "success": True,
            "path": str(p),
            "readonly": bool(attrs & 1),
            "hidden": bool(attrs & 2),
            "system": bool(attrs & 4),
            "directory": bool(attrs & 16),
            "archive": bool(attrs & 32)
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def modify_supported_file_attributes(
    path: str,
    readonly: Optional[bool] = None,
    hidden: Optional[bool] = None
) -> Dict[str, Any]:
    """Modify Windows file attributes (hidden, readonly) using attrib."""
    if not check_permission("modify_supported_file_attributes", PermissionLevel.ACTION, {"path": path}):
        return {"success": False, "error": "Permission denied"}
    try:
        p = _normalize_path(path)
        if not p.exists():
            return {"success": False, "error": f"Path '{path}' does not exist."}

        cmd_parts = ["attrib"]
        if readonly is not None:
            cmd_parts.append("+r" if readonly else "-r")
        if hidden is not None:
            cmd_parts.append("+h" if hidden else "-h")
        cmd_parts.append(str(p))

        res = subprocess.run(cmd_parts, capture_output=True, text=True, timeout=5)
        return {"success": res.returncode == 0, "path": str(p), "message": "Updated attributes."}
    except Exception as e:
        return {"success": False, "error": str(e)}


def inspect_file_timestamps(path: str) -> Dict[str, Any]:
    """Inspect precision creation, modification, and access timestamps."""
    return get_file_info(path)


def inspect_disk_usage(path: str = ".") -> Dict[str, Any]:
    """Inspect drive storage capacity, used space, and free space for a path."""
    if not check_permission("inspect_disk_usage", PermissionLevel.READ, {"path": path}):
        return {"success": False, "error": "Permission denied"}
    try:
        p = _normalize_path(path)
        usage = shutil.disk_usage(str(p))
        return {
            "success": True,
            "path": str(p),
            "total_gb": round(usage.total / (1024**3), 2),
            "used_gb": round(usage.used / (1024**3), 2),
            "free_gb": round(usage.free / (1024**3), 2),
            "percent_used": round((usage.used / usage.total) * 100, 1)
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


# ============================================================================
# Category G: Windows File Explorer & Shell Automation
# ============================================================================

def file_explorer_open(folder_path: str = "") -> Dict[str, Any]:
    """Open File Explorer at specified folder or user home directory."""
    if not check_permission("file_explorer_open", PermissionLevel.LOW_RISK, {"folder_path": folder_path}):
        return {"success": False, "error": "Permission denied"}
    try:
        p = _normalize_path(folder_path) if folder_path else Path.home()
        if not p.is_dir():
            p = p.parent

        subprocess.Popen(["explorer.exe", str(p)])
        return {"success": True, "message": f"Opened File Explorer at '{p}'", "path": str(p)}
    except Exception as e:
        return {"success": False, "error": str(e)}


def file_explorer_reveal(path: str) -> Dict[str, Any]:
    """Open Windows File Explorer with the specific file or folder highlighted/selected."""
    if not check_permission("file_explorer_reveal", PermissionLevel.LOW_RISK, {"path": path}):
        return {"success": False, "error": "Permission denied"}
    try:
        p = _normalize_path(path)
        if not p.exists():
            return {"success": False, "error": f"Path '{path}' does not exist."}

        # explorer.exe /select,"C:\path\to\file.ext"
        subprocess.Popen(["explorer.exe", f"/select,{p}"])
        return {"success": True, "message": f"Revealed '{p.name}' in File Explorer.", "path": str(p)}
    except Exception as e:
        return {"success": False, "error": str(e)}


def file_explorer_navigate(folder_path: str, window_title: Optional[str] = None) -> Dict[str, Any]:
    """Navigate an existing File Explorer window to a new folder path via COM or UIA."""
    if not check_permission("file_explorer_navigate", PermissionLevel.ACTION, {"folder_path": folder_path}):
        return {"success": False, "error": "Permission denied"}
    try:
        target = _normalize_path(folder_path)
        if not target.is_dir():
            return {"success": False, "error": f"Directory '{folder_path}' does not exist."}

        # Use Shell.Application COM to find explorer window and navigate
        ps_cmd = (
            f'$shell = New-Object -ComObject Shell.Application; '
            f'$wins = $shell.Windows(); '
            f'$navigated = $false; '
            f'foreach ($w in $wins) {{ '
            f'  if ($w.Name -match "Explorer") {{ '
            f'    $w.Navigate2("{target}"); '
            f'    $navigated = $true; '
            f'    break; '
            f'  }} '
            f'}}; '
            f'Write-Output $navigated'
        )
        res = subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True, text=True, timeout=10)
        if "True" in res.stdout:
            return {"success": True, "message": f"Navigated File Explorer window to '{target}'"}
        
        # If no open window found, open new one
        return file_explorer_open(str(target))
    except Exception as e:
        return {"success": False, "error": str(e)}


def file_explorer_get_selection() -> Dict[str, Any]:
    """Get the currently selected files or folders in active Windows File Explorer window."""
    if not check_permission("file_explorer_get_selection", PermissionLevel.READ, {}):
        return {"success": False, "error": "Permission denied"}
    try:
        ps_cmd = (
            '$shell = New-Object -ComObject Shell.Application; '
            '$wins = $shell.Windows(); '
            '$selected = @(); '
            'foreach ($w in $wins) { '
            '  if ($w.Name -match "Explorer") { '
            '    foreach ($item in $w.Document.SelectedItems()) { '
            '      $selected += $item.Path '
            '    } '
            '    break '
            '  } '
            '}; '
            '$selected | ConvertTo-Json -Compress'
        )
        res = subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True, text=True, timeout=10)
        items = []
        if res.returncode == 0 and res.stdout.strip():
            try:
                parsed = json.loads(res.stdout.strip())
                items = [parsed] if isinstance(parsed, str) else parsed
            except Exception:
                pass
        return {"success": True, "count": len(items), "selected_paths": items}
    except Exception as e:
        return {"success": False, "error": str(e)}


def file_open_with(path: str, app_name: Optional[str] = None) -> Dict[str, Any]:
    """Open a file with a specific application or invoke the Windows native 'Open with...' dialog."""
    if not check_permission("file_open_with", PermissionLevel.LOW_RISK, {"path": path, "app": app_name}):
        return {"success": False, "error": "Permission denied"}
    try:
        p = _normalize_path(path)
        if not p.exists():
            return {"success": False, "error": f"Path '{path}' does not exist."}

        if app_name:
            subprocess.Popen([app_name, str(p)])
            return {"success": True, "message": f"Opened '{p.name}' with '{app_name}'."}
        else:
            # Trigger native Windows OpenAs dialog
            subprocess.Popen(["rundll32.exe", "shell32.dll,OpenAs_RunDLL", str(p)])
            return {"success": True, "message": f"Opened native 'Open with' dialog for '{p.name}'."}
    except Exception as e:
        return {"success": False, "error": str(e)}


def file_share(path: str) -> Dict[str, Any]:
    """Open Windows file sharing properties dialog for the path."""
    if not check_permission("file_share", PermissionLevel.LOW_RISK, {"path": path}):
        return {"success": False, "error": "Permission denied"}
    try:
        p = _normalize_path(path)
        if not p.exists():
            return {"success": False, "error": f"Path '{path}' does not exist."}

        # Open Properties dialog with Sharing tab
        ps_cmd = (
            f'$shell = New-Object -ComObject Shell.Application; '
            f'$folder = $shell.Namespace("{p.parent}"); '
            f'$item = $folder.ParseName("{p.name}"); '
            f'$item.InvokeVerb("properties")'
        )
        subprocess.Popen(["powershell", "-NoProfile", "-Command", ps_cmd])
        return {"success": True, "message": f"Opened Windows properties/sharing dialog for '{p.name}'."}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ============================================================================
# Backward Compatibility Wrappers
# ============================================================================

def read_file(path: str) -> Dict[str, Any]:
    res = read_text_file(path)
    if res.get("success"):
        return {"success": True, "path": res["path"], "content": res["content"]}
    return res


def write_file(path: str, content: str) -> Dict[str, Any]:
    return write_text_file(path, content, atomic=True)


def file_search(query: str, root_dir: str = ".") -> Dict[str, Any]:
    res = search_files(query, root_dir)
    if res.get("success"):
        return {"success": True, "root": res["root_dir"], "matches": [m["path"] for m in res["matches"]]}
    return res


def file_exists(path: str) -> Dict[str, Any]:
    return check_path_exists(path)


def file_delete(path: str) -> Dict[str, Any]:
    return move_to_recycle_bin(path)
