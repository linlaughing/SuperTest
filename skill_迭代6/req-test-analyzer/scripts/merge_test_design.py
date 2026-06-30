#!/usr/bin/env python3
"""
merge_test_design.py - 阶段3b用例合并脚本

合并所有batch用例文件 + 场景文件，生成：
- test_design.json（聚合用例）
- scene_tc_mapping.json（场景-用例映射）
- e2e_scenes.json（可选，合并后的场景文件）
"""

import argparse
import json
import os
import sys
from pathlib import Path
from collections import defaultdict


def load_json(path: str) -> dict | list:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: str, data, indent=2):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=indent)


def glob_batch_files(output_dir: str) -> list[str]:
    """扫描test_design_batch_*.json文件。"""
    d = Path(output_dir)
    return sorted(str(f) for f in d.glob("test_design_batch_*.json"))


def load_all_test_cases(batch_files: list[str]) -> list[dict]:
    """加载所有batch文件中的用例。支持多种字段名。"""
    cases = []
    for fpath in batch_files:
        data = load_json(fpath)
        if isinstance(data, list):
            cases.extend(data)
        elif isinstance(data, dict):
            # 兼容多种字段名：cases / test_cases
            for key in ["cases", "test_cases"]:
                if key in data and isinstance(data[key], list):
                    cases.extend(data[key])
                    break
    return cases


def build_scene_tc_mapping(cases: list[dict]) -> dict:
    """构建场景→用例映射。"""
    mapping = defaultdict(list)
    for case in cases:
        source_scene = case.get("source_scene", "")
        if source_scene:
            mapping[source_scene].append(case["case_id"])
    return dict(mapping)


def count_by_type(cases: list[dict]) -> dict:
    """按test_type统计用例数。"""
    counts = defaultdict(int)
    for case in cases:
        tt = case.get("test_type", "unknown")
        counts[tt] += 1
    return dict(counts)


def validate_coverage(cases: list[dict], enriched_index: dict, framework_data: dict) -> list[str]:
    """验证场景覆盖完整性，返回缺失场景列表。"""
    errors = []

    # 获取所有场景ID
    scene_ids = set()

    # 从enriched索引获取flow场景ID
    for si in enriched_index.get("scenario_index", []):
        scene_ids.add(si.get("id", ""))

    # 从framework数据获取framework场景ID
    for fs in framework_data.get("framework_scenarios", []):
        scene_ids.add(fs.get("id", ""))

    # 获取已覆盖的场景ID
    covered = set(case.get("source_scene", "") for case in cases)

    # 计算缺失
    missing = scene_ids - covered - {"", None}

    if missing:
        errors.append(f"缺失场景覆盖: {list(missing)[:10]}")

    return errors, list(missing)


def merge_scenes(enriched_dir: str, enriched_index: dict, framework_data: dict) -> list[dict]:
    """合并所有场景文件，用于生成e2e_scenes.json（可选）。"""
    scenarios = []

    # 加载enriched场景
    d = Path(enriched_dir)
    for f in sorted(d.glob("FS-*.json")):
        scenarios.append(load_json(str(f)))

    # 添加framework场景
    scenarios.extend(framework_data.get("framework_scenarios", []))

    return scenarios


def main():
    parser = argparse.ArgumentParser(description="合并测试用例和场景")
    parser.add_argument("--output-dir", required=True, help="输出目录")
    parser.add_argument("--generate-e2e", action="store_true", help="是否生成e2e_scenes.json")
    args = parser.parse_args()

    output_dir = args.output_dir

    # 1. 加载所有batch用例
    batch_files = glob_batch_files(output_dir)
    print(f"发现batch文件: {len(batch_files)}")

    all_cases = load_all_test_cases(batch_files)
    print(f"总用例数: {len(all_cases)}")

    # 2. 加载enriched索引和framework数据（用于覆盖验证）
    enriched_index = {}
    enriched_dir = os.path.join(output_dir, ".state", "s3a_enriched")
    enriched_index_path = os.path.join(output_dir, ".state", "s3a_enriched_index.json")

    if os.path.exists(enriched_index_path):
        enriched_index = load_json(enriched_index_path)

    framework_data = {}
    framework_path = os.path.join(output_dir, ".state", "s3a_framework.json")
    if os.path.exists(framework_path):
        framework_data = load_json(framework_path)

    # 3. 覆盖验证
    errors, missing = validate_coverage(all_cases, enriched_index, framework_data)
    if errors:
        print(f"[WARN] 覆盖验证发现问题:")
        for e in errors:
            print(f"  - {e}")
    else:
        print("[OK] 场景覆盖验证通过")

    # 4. 生成test_design.json
    test_design_path = os.path.join(output_dir, "test_design.json")
    save_json(test_design_path, all_cases)
    print(f"输出: {test_design_path}")

    # 5. 生成scene_tc_mapping.json
    mapping = build_scene_tc_mapping(all_cases)
    scene_total = len(set(case.get("source_scene", "") for case in all_cases if case.get("source_scene")))

    mapping_data = {
        "scene_total": scene_total,
        "tc_total": len(all_cases),
        "coverage": f"{len(mapping)}/{scene_total * 100 if scene_total else 100:.0f}%",
        "mapping": mapping,
        "missing_scenes": missing
    }

    mapping_path = os.path.join(output_dir, "scene_tc_mapping.json")
    save_json(mapping_path, mapping_data)
    print(f"输出: {mapping_path}")

    # 6. 可选：生成e2e_scenes.json
    if args.generate_e2e:
        scenarios = merge_scenes(enriched_dir, enriched_index, framework_data)
        e2e_data = {
            "meta": enriched_index.get("meta", {}),
            "function_points": enriched_index.get("function_points", []),
            "flow_scenarios": scenarios
        }
        e2e_path = os.path.join(output_dir, "e2e_scenes.json")
        save_json(e2e_path, e2e_data)
        print(f"输出: {e2e_path}")

    # 7. 统计摘要
    type_counts = count_by_type(all_cases)
    print(f"\n## S3b-merge完成摘要")
    print(f"| 项目 | 结果 |")
    print(f"|------|------|")
    print(f"| 场景输入 | {scene_total} |")
    print(f"| 用例输出 | {len(all_cases)} |")
    print(f"| 正常用例 | {type_counts.get('正常E2E', 0)} |")
    print(f"| 变体用例 | {type_counts.get('变体E2E', 0)} |")
    print(f"| 异常用例 | {type_counts.get('异常E2E', 0)} |")
    print(f"| 边界用例 | {type_counts.get('边界E2E', 0)} |")
    print(f"| 质量用例 | {type_counts.get('质量E2E', 0)} |")
    print(f"| 约束用例 | {type_counts.get('约束E2E', 0)} |")
    print(f"| 交叉用例 | {type_counts.get('交叉E2E', 0)} |")
    print(f"| 覆盖率 | {mapping_data['coverage']} |")
    print(f"| missing_scenes | {missing[:5] if missing else []} |")

    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())