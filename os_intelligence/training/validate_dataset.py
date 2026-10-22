"""
os_intelligence/training/validate_dataset.py
=========================================
Validates the structural integrity, tool consistency, schema compliance,
and leakage separation of the generated JARVIS PC-Expert SLM datasets.
"""

import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

DATA_DIR = Path(__file__).parent.parent / "data"

EXPECTED_DOMAINS = {
    "Domain A: Computer Fundamentals",
    "Domain B: PC Interaction Behavior",
    "Domain C: State-Aware Reasoning",
    "Domain D: Task Planning & Dependencies",
    "Domain E: Failure Recovery",
}


def validate_file(filepath: Path) -> Tuple[bool, int, Set[str]]:
    print(f"\n--- Validating: {filepath.name} ---")
    if not filepath.exists():
        raise FileNotFoundError(f"Missing dataset file: {filepath}")

    groups: Set[str] = set()
    total_samples = 0
    total_turns = 0
    total_tool_calls = 0
    domains_seen: Dict[str, int] = {}
    errors: List[str] = []

    with open(filepath, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue

            try:
                sample = json.loads(line)
            except json.JSONDecodeError as exc:
                errors.append(f"Line {line_num}: JSON decode error: {exc}")
                continue

            total_samples += 1

            # 1. Required keys
            for key in ["id", "scenario_group", "domain", "tools", "messages"]:
                if key not in sample:
                    errors.append(f"Line {line_num}: Missing required field '{key}'")

            sample_id = sample.get("id", f"line_{line_num}")
            grp = sample.get("scenario_group")
            if grp:
                groups.add(grp)

            # 2. Domain check
            dom = sample.get("domain", "")
            if dom not in EXPECTED_DOMAINS:
                errors.append(f"Sample {sample_id}: Unknown domain '{dom}'")
            domains_seen[dom] = domains_seen.get(dom, 0) + 1

            # 3. Tools check
            tools = sample.get("tools", [])
            if not isinstance(tools, list) or len(tools) == 0:
                errors.append(f"Sample {sample_id}: 'tools' must be a non-empty list")

            tool_names = set()
            for t in tools:
                if not isinstance(t, dict) or "name" not in t or "parameters" not in t:
                    errors.append(f"Sample {sample_id}: Malformed tool definition: {t}")
                else:
                    tool_names.add(t["name"])

            # 4. Messages check
            messages = sample.get("messages", [])
            if not isinstance(messages, list) or len(messages) < 2:
                errors.append(f"Sample {sample_id}: 'messages' must have at least 2 turns")

            prev_role = None
            for idx, msg in enumerate(messages):
                role = msg.get("role")
                content = msg.get("content", "")
                total_turns += 1

                if role not in ["user", "model", "tool", "assistant"]:
                    errors.append(f"Sample {sample_id}: Message {idx} has invalid role '{role}'")

                # Validate tool calls in model turns
                if role in ["model", "assistant"]:
                    matches = re.findall(r"call:(\w+)\s*(\{.*?\})", content, re.DOTALL)
                    for call_tool, call_args in matches:
                        total_tool_calls += 1
                        if call_tool not in tool_names:
                            errors.append(
                                f"Sample {sample_id}: Tool '{call_tool}' called but not present in tool schema list {list(tool_names)}"
                            )
                        try:
                            json.loads(call_args)
                        except json.JSONDecodeError:
                            errors.append(f"Sample {sample_id}: Tool call args not valid JSON: '{call_args}'")

                prev_role = role

    if errors:
        print(f"Validation FAILED with {len(errors)} error(s):")
        for err in errors[:10]:
            print(f"  - {err}")
        if len(errors) > 10:
            print(f"  ... and {len(errors) - 10} more errors.")
        return False, total_samples, groups

    print(f"VALID: {total_samples} samples, {total_turns} total turns, {total_tool_calls} tool calls, {len(groups)} unique groups.")
    print("Domain distribution:")
    for d, count in domains_seen.items():
        print(f"  - {d}: {count}")

    return True, total_samples, groups


def main():
    print("=== JARVIS PC-Expert SLM Dataset Validator ===")
    train_path = DATA_DIR / "train.jsonl"
    val_path = DATA_DIR / "val.jsonl"
    test_path = DATA_DIR / "test.jsonl"

    ok_train, n_train, grp_train = validate_file(train_path)
    ok_val, n_val, grp_val = validate_file(val_path)
    ok_test, n_test, grp_test = validate_file(test_path)

    if not (ok_train and ok_val and ok_test):
        print("\nDataset validation encountered errors.")
        sys.exit(1)

    # 5. Leakage check between splits
    print("\n--- Leakage Separation Check ---")
    train_val_overlap = grp_train.intersection(grp_val)
    train_test_overlap = grp_train.intersection(grp_test)
    val_test_overlap = grp_val.intersection(grp_test)

    if train_val_overlap or train_test_overlap or val_test_overlap:
        print(f"LEAKAGE DETECTED! Overlapping scenario groups found:")
        if train_val_overlap:
            print(f"  Train & Val overlap: {train_val_overlap}")
        if train_test_overlap:
            print(f"  Train & Test overlap: {train_test_overlap}")
        if val_test_overlap:
            print(f"  Val & Test overlap: {val_test_overlap}")
        sys.exit(1)
    else:
        print("PASS: Zero leakage across Train, Val, and Test splits. Group boundaries strictly preserved.")

    print("\nDataset is 100% compliant and ready for training!")


if __name__ == "__main__":
    main()
