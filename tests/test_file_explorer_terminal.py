"""
tests/test_file_explorer_terminal.py  -  Enterprise Unit & Integration Tests for Filesystem & File Explorer
=============================================================================================================
"""

import os
import sys
import tempfile
import json
import pytest
from pathlib import Path

from app.tools.bus import tool_bus
from app.tools.registry import register_all_tools
from app.local_brain import local_brain
from app.router import plan_user_input, ExecutionContext
import app.tools.filesystem as fs
import app.tools.terminal as term


@pytest.fixture(scope="module", autouse=True)
def init_system():
    register_all_tools()
    local_brain._refresh_schema_cache()
    from app.permissions import permission_engine
    permission_engine.set_approval_handler(lambda *args, **kwargs: True)


# ---------------------------------------------------------------------------
# 1. UnifiedToolBus Registration Tests
# ---------------------------------------------------------------------------

def test_filesystem_tools_registered_in_bus():
    """Verify all new filesystem and file explorer tools are registered in UnifiedToolBus."""
    required_tools = [
        "get_current_directory", "change_directory", "list_directory", "search_files",
        "search_file_contents", "get_file_info", "get_directory_tree", "find_recent_files",
        "find_large_files", "find_empty_directories", "find_duplicate_files", "compare_files",
        "compare_directories", "check_path_exists", "inspect_file_permissions",
        "create_file", "create_directory", "create_directory_tree", "create_project_structure",
        "create_shortcut", "create_temporary_file", "rename_path", "copy_file",
        "copy_directory", "move_file", "move_directory", "duplicate_file", "batch_rename",
        "batch_copy", "batch_move", "move_to_recycle_bin", "restore_from_recycle_bin",
        "inspect_recycle_bin", "permanently_delete", "delete_empty_directory",
        "undo_supported_file_operation", "read_text_file", "write_text_file",
        "append_text_file", "edit_text_file", "replace_text", "read_json_file",
        "write_json_file", "read_configuration_file", "write_configuration_file",
        "inspect_source_file", "apply_approved_file_changes", "create_zip_archive",
        "extract_zip_archive", "inspect_archive", "calculate_file_hash", "compare_file_hashes",
        "inspect_file_attributes", "modify_supported_file_attributes", "inspect_disk_usage",
        "file_explorer_open", "file_explorer_reveal", "file_explorer_navigate",
        "file_explorer_get_selection", "file_open_with", "file_share",
        "terminal_execute", "execute_and_validate"
    ]
    for name in required_tools:
        assert name in tool_bus.tools, f"Missing tool in tool_bus: {name}"
        tdef = tool_bus.tools[name]
        assert len(tdef.description) > 5


# ---------------------------------------------------------------------------
# 2. Category A: Discovery & Inspection
# ---------------------------------------------------------------------------

def test_directory_discovery_and_tree():
    with tempfile.TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir)
        (root / "folder_a").mkdir()
        (root / "folder_b").mkdir()
        (root / "folder_a" / "doc.txt").write_text("JARVIS test content", encoding="utf-8")
        (root / "folder_a" / "code.py").write_text("print('hello')", encoding="utf-8")

        # 1. list_directory
        res_list = fs.list_directory(str(root), recursive=True, max_depth=2)
        assert res_list["success"] is True
        assert res_list["total_count"] >= 3

        # 2. search_files
        res_search = fs.search_files("doc", root_dir=str(root))
        assert res_search["success"] is True
        assert res_search["total_matches"] >= 1
        assert "doc.txt" in res_search["matches"][0]["name"]

        # 3. search_file_contents
        res_content = fs.search_file_contents("JARVIS", root_dir=str(root))
        assert res_content["success"] is True
        assert len(res_content["results"]) >= 1

        # 4. get_directory_tree
        res_tree = fs.get_directory_tree(str(root))
        assert res_tree["success"] is True
        assert "folder_a" in res_tree["tree"]

        # 5. get_file_info
        res_info = fs.get_file_info(str(root / "folder_a" / "doc.txt"))
        assert res_info["success"] is True
        assert res_info["is_file"] is True
        assert res_info["extension"] == ".txt"


def test_find_empty_and_duplicate_files():
    with tempfile.TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir)
        (root / "empty_dir").mkdir()
        f1 = root / "orig.txt"
        f2 = root / "dup.txt"
        content = "Duplicate check string for testing JARVIS hash logic." * 20
        f1.write_text(content, encoding="utf-8")
        f2.write_text(content, encoding="utf-8")

        # Empty dir
        res_empty = fs.find_empty_directories(str(root))
        assert res_empty["success"] is True
        assert any("empty_dir" in p for p in res_empty["empty_directories"])

        # Duplicate files
        res_dup = fs.find_duplicate_files(str(root), min_size_bytes=10)
        assert res_dup["success"] is True
        assert len(res_dup["duplicates"]) >= 1


def test_compare_files_and_directories():
    with tempfile.TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir)
        d1 = root / "dir1"
        d2 = root / "dir2"
        d1.mkdir()
        d2.mkdir()

        (d1 / "same.txt").write_text("Same content", encoding="utf-8")
        (d2 / "same.txt").write_text("Same content", encoding="utf-8")
        (d1 / "diff.txt").write_text("Hello A", encoding="utf-8")
        (d2 / "diff.txt").write_text("Hello B", encoding="utf-8")

        # Compare files
        res_cmp = fs.compare_files(str(d1 / "diff.txt"), str(d2 / "diff.txt"))
        assert res_cmp["success"] is True
        assert res_cmp["identical"] is False
        assert "diff" in res_cmp

        # Compare directories
        res_d_cmp = fs.compare_directories(str(d1), str(d2))
        assert res_d_cmp["success"] is True
        assert "diff.txt" in res_d_cmp["modified_in_both"]


# ---------------------------------------------------------------------------
# 3. Category B & C: Creation, Rename, Copy, Move, Batch Operations
# ---------------------------------------------------------------------------

def test_file_and_directory_creation():
    with tempfile.TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir)

        # 1. create_file
        res_cf = fs.create_file(str(root / "new_file.txt"), content="Created successfully")
        assert res_cf["success"] is True
        assert (root / "new_file.txt").is_file()

        # 2. create_directory_tree
        res_dt = fs.create_directory_tree(str(root), ["src/controllers", "src/models", "tests"])
        assert res_dt["success"] is True
        assert (root / "src" / "controllers").is_dir()

        # 3. create_project_structure
        schema = {
            "app": {
                "__init__.py": "# package",
                "main.py": "print('running')"
            },
            "README.md": "# Project"
        }
        res_proj = fs.create_project_structure(str(root / "my_project"), schema)
        assert res_proj["success"] is True
        assert (root / "my_project" / "app" / "main.py").is_file()


def test_rename_copy_move_and_batch():
    with tempfile.TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir)
        src = root / "source.txt"
        src.write_text("Content to move/copy", encoding="utf-8")

        # 1. copy_file
        copied = root / "copied.txt"
        res_copy = fs.copy_file(str(src), str(copied))
        assert res_copy["success"] is True
        assert copied.is_file()

        # 2. rename_path
        renamed = root / "renamed.txt"
        res_rename = fs.rename_path(str(copied), str(renamed))
        assert res_rename["success"] is True
        assert renamed.is_file()
        assert not copied.exists()

        # 3. move_file
        sub = root / "subdir"
        sub.mkdir()
        res_move = fs.move_file(str(renamed), str(sub))
        assert res_move["success"] is True
        assert (sub / "renamed.txt").is_file()
        assert not renamed.exists()

        # 4. duplicate_file
        res_dup = fs.duplicate_file(str(src))
        assert res_dup["success"] is True
        assert Path(res_dup["duplicate"]).is_file()


# ---------------------------------------------------------------------------
# 4. Category D: Delete, Recovery & Undo
# ---------------------------------------------------------------------------

def test_undo_operation():
    with tempfile.TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir)
        target = root / "file_for_undo.txt"
        target.write_text("Original text before edit", encoding="utf-8")

        # Perform an edit with backup
        res_edit = fs.edit_text_file(str(target), 1, 1, "Modified text line")
        assert res_edit["success"] is True
        assert "Modified text line" in target.read_text(encoding="utf-8")

        # Undo the edit
        res_undo = fs.undo_supported_file_operation(res_edit["operation_id"])
        assert res_undo["success"] is True
        assert "Original text before edit" in target.read_text(encoding="utf-8")


def test_permanent_delete():
    with tempfile.TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir)
        f = root / "to_delete.txt"
        f.write_text("delete me", encoding="utf-8")

        res_del = fs.permanently_delete(str(f))
        assert res_del["success"] is True
        assert not f.exists()


# ---------------------------------------------------------------------------
# 5. Category E: Content Operations (Text, JSON, Config, Source)
# ---------------------------------------------------------------------------

def test_content_operations():
    with tempfile.TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir)
        p = root / "doc.txt"

        # 1. atomic write & read
        fs.write_text_file(str(p), "Line 1\nLine 2\nLine 3\n", atomic=True)
        res_read = fs.read_text_file(str(p), offset=0, limit=2)
        assert res_read["success"] is True
        assert res_read["returned_lines"] == 2

        # 2. append
        fs.append_text_file(str(p), "Line 4\n")
        assert "Line 4" in p.read_text(encoding="utf-8")

        # 3. replace text
        fs.replace_text(str(p), "Line 2", "Modified Line 2")
        assert "Modified Line 2" in p.read_text(encoding="utf-8")

        # 4. JSON
        j_path = root / "data.json"
        data = {"app": "JARVIS", "version": "0.5.2", "enabled": True}
        fs.write_json_file(str(j_path), data)
        res_j = fs.read_json_file(str(j_path))
        assert res_j["success"] is True
        assert res_j["data"]["app"] == "JARVIS"

        # 5. Configuration .env
        env_path = root / ".env"
        fs.write_configuration_file(str(env_path), {"PORT": "8000", "ENV": "development"})
        res_env = fs.read_configuration_file(str(env_path))
        assert res_env["success"] is True
        assert res_env["data"]["PORT"] == "8000"

        # 6. Source inspection
        py_path = root / "sample.py"
        py_path.write_text(
            "import os\n\nclass SampleBot:\n    def run(self):\n        pass\n",
            encoding="utf-8"
        )
        res_src = fs.inspect_source_file(str(py_path))
        assert res_src["success"] is True
        assert "SampleBot" in res_src["classes"]
        assert "run" in res_src["functions"]


# ---------------------------------------------------------------------------
# 6. Category F: Archives (ZIP & Anti-ZipSlip Protection)
# ---------------------------------------------------------------------------

def test_zip_archive_creation_and_extraction():
    with tempfile.TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir)
        src_dir = root / "pack"
        src_dir.mkdir()
        (src_dir / "file1.txt").write_text("Hello from archive 1", encoding="utf-8")
        (src_dir / "file2.txt").write_text("Hello from archive 2", encoding="utf-8")

        arc_file = root / "bundle.zip"
        res_zip = fs.create_zip_archive([str(src_dir / "file1.txt"), str(src_dir / "file2.txt")], str(arc_file))
        assert res_zip["success"] is True
        assert arc_file.is_file()

        # Inspect
        res_insp = fs.inspect_archive(str(arc_file))
        assert res_insp["success"] is True
        assert res_insp["total_entries"] == 2

        # Extract
        out_dir = root / "unpacked"
        res_ext = fs.extract_zip_archive(str(arc_file), str(out_dir))
        assert res_ext["success"] is True
        assert (out_dir / "file1.txt").is_file()


# ---------------------------------------------------------------------------
# 7. Category H: Terminal OS Subprocess & Validation
# ---------------------------------------------------------------------------

def test_terminal_execute_and_validation():
    # 1. Terminal execute basic echo
    res = term.terminal_execute("Write-Output 'JARVIS_TERMINAL_TEST'")
    assert res["success"] is True
    assert "JARVIS_TERMINAL_TEST" in res["stdout"]

    # 2. execute_and_validate with output_contains
    res_val = term.execute_and_validate(
        command="Write-Output 'VALIDATION_STRING_123'",
        validation_type="output_contains",
        expected_pattern="VALIDATION_STRING_123"
    )
    assert res_val["success"] is True
    assert res_val["validated"] is True

    # 3. execute_and_validate with file creation
    with tempfile.TemporaryDirectory() as tmp_dir:
        target_f = Path(tmp_dir) / "term_created.txt"
        cmd = f"New-Item -Path '{str(target_f)}' -ItemType File -Value 'Terminal Created'"
        res_f_val = term.execute_and_validate(
            command=cmd,
            validation_type="file_created",
            check_path=str(target_f)
        )
        assert res_f_val["success"] is True
        assert res_f_val["validated"] is True
        assert target_f.is_file()


# ---------------------------------------------------------------------------
# 8. Natural Language Router Fast-Path Integration
# ---------------------------------------------------------------------------

def test_router_file_explorer_intent_mapping():
    ctx = ExecutionContext()

    # list files
    steps = plan_user_input("list files", ctx)
    assert len(steps) == 1
    assert steps[0].tool_name == "list_directory"

    # change directory
    steps_cd = plan_user_input("cd my_folder", ctx)
    assert len(steps_cd) == 1
    assert steps_cd[0].tool_name == "change_directory"
    assert steps_cd[0].tool_args.get("path") == "my_folder"

    # create folder
    steps_mkdir = plan_user_input("create folder AI Projects", ctx)
    assert len(steps_mkdir) == 1
    assert steps_mkdir[0].tool_name == "create_directory"
    assert steps_mkdir[0].tool_args.get("path") == "AI Projects"

    # rename file
    steps_rn = plan_user_input("rename file old.txt to new.txt", ctx)
    assert len(steps_rn) == 1
    assert steps_rn[0].tool_name == "rename_path"
    assert steps_rn[0].tool_args.get("source") == "old.txt"
    assert steps_rn[0].tool_args.get("new_name_or_path") == "new.txt"

    # move file
    steps_mv = plan_user_input("move file report.pdf into Documents", ctx)
    assert len(steps_mv) == 1
    assert steps_mv[0].tool_name == "move_file"
    assert steps_mv[0].tool_args.get("source") == "report.pdf"
    assert steps_mv[0].tool_args.get("destination") in ("Documents", str(Path.home() / "Documents"))

    # recycle file
    steps_rc = plan_user_input("recycle file temp.txt", ctx)
    assert len(steps_rc) == 1
    assert steps_rc[0].tool_name == "move_to_recycle_bin"

    # open explorer
    steps_exp = plan_user_input("open explorer", ctx)
    assert len(steps_exp) == 1
    assert steps_exp[0].tool_name == "file_explorer_open"

    # terminal command
    steps_cmd = plan_user_input("run command git status", ctx)
    assert len(steps_cmd) == 1
    assert steps_cmd[0].tool_name == "terminal_execute"
    assert "git status" in steps_cmd[0].tool_args.get("command", "")


@pytest.mark.asyncio
async def test_core_process_request_list_files_output():
    """Verify that JarvisCore.process_request actually outputs the files and folders to the user."""
    from app.core import JarvisCore

    core = JarvisCore(None)

    # 1. Test "list files"
    history, response = await core.process_request("list files", [])
    assert "[list_directory] ✔" in response
    assert "Directory:" in response
    # Should list files or directories with folder/file icons
    assert ("📁 [DIR]" in response) or ("📄 [FILE]" in response) or ("(empty directory)" in response)

    # 2. Test "list file folders"
    history, response2 = await core.process_request("list file folders", [])
    assert "[list_directory] ✔" in response2
    assert "Directory:" in response2
    assert ("📁 [DIR]" in response2) or ("📄 [FILE]" in response2) or ("(empty directory)" in response2)

