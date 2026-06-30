#!/usr/bin/env python3
"""
aggregate_results.py - 阶段4-agg：结果聚合

读取 .state/results/*.json，生成 case_results.json。
替代原 Agent 方式，执行时间 <1s。

用法：
    python aggregate_results.py --output-dir <dir>
"""

import argparse
import json
import os
import sys
from glob import glob


def load_json(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: str, data, indent=2):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=indent)


def classify_status(raw_status: str) -> str:
    """统一 status 字段（处理大小写不一致）。"""
    s = raw_status.strip().upper()
    if s == "PASS":
        return "passed"
    return raw_status.strip().lower()


def aggregate(output_dir: str):
    state_dir = os.path.join(output_dir, ".state")
    results_dir = os.path.join(state_dir, "results")

    # 读取所有结果文件
    details = {}
    for fp in sorted(glob(os.path.join(results_dir, "*.json"))):
        r = load_json(fp)
        case_id = os.path.basename(fp).replace(".json", "")
        status = classify_status(r.get("status", "unknown"))
        details[case_id] = {
            "status": status,
            "fix_rounds": r.get("fix_rounds", 0),
        }
        if r.get("sdk_bug"):
            details[case_id]["sdk_bug"] = r["sdk_bug"]
        if r.get("mock_file"):
            details[case_id]["mock_file"] = r["mock_file"]

    # 统计
    total = len(details)
    passed = sum(1 for d in details.values() if d["status"] == "passed")
    sdk_defects = sum(1 for d in details.values() if "sdk_bug" in d["status"] or "defect" in d["status"])
    failed = sum(1 for d in details.values() if d["status"] == "failed")
    env_issues = sum(1 for d in details.values() if "env_issue" in d["status"])
    # passed 含 sdk_bug_found（通过了但发现了缺陷）
    pass_count = passed + sdk_defects

    case_results = {
        "summary": {
            "total": total,
            "passed": pass_count,
            "sdk_defects": sdk_defects,
            "failed": failed,
            "env_issues": env_issues,
        },
        "details": details,
    }

    # 写入
    output_path = os.path.join(output_dir, "case_results.json")
    save_json(output_path, case_results)

    # 输出摘要
    print(f"Total: {total} | Passed: {pass_count} | SDK defects: {sdk_defects} | Failed: {failed}")
    print(f"Output: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="阶段4-agg 结果聚合")
    parser.add_argument("--output-dir", required=True, help="输出目录")
    args = parser.parse_args()
    aggregate(args.output_dir)


if __name__ == "__main__":
    main()
