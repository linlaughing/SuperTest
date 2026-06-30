#!/usr/bin/env python3
"""
merge_enriched.py - 阶段3a富化场景合并脚本

合并2个批次摘要 + fp_mapping + s1_index，生成：
- s3a_enriched_index.json（富化索引）

优化版：支持2-Agent并行富化后的合并。
"""

import json
import os
import sys
from pathlib import Path


def load_json(path: str) -> dict | list:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: str, data, indent=2):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=indent)


def glob_batch_summaries(output_dir: str) -> list[dict]:
    """扫描s3a_batch_*_summary.json文件。"""
    d = Path(output_dir) / ".state"
    summaries = []
    for f in d.glob("s3a_batch_*_summary.json"):
        summaries.append(load_json(str(f)))
    return summaries


def build_enriched_index(s1_index: dict, fp_mapping: dict, batch_summaries: list[dict], output_dir: str) -> dict:
    """构建s3a_enriched_index.json。"""

    # 合并所有enriched_stats
    all_stats = {}
    all_scene_ids = []
    all_gap_ids = []

    for summary in batch_summaries:
        all_scene_ids.extend(summary.get("scene_ids", []))
        all_gap_ids.extend(summary.get("gap_ids", []))
        for scene_id, stats in summary.get("enriched_stats", {}).items():
            all_stats[scene_id] = stats

    # 构建scenario_index
    scenario_index = []
    enriched_dir = Path(output_dir) / ".state" / "s3a_enriched"

    for scene_id in all_scene_ids + all_gap_ids:
        # 确定场景类型
        if scene_id.startswith("FS-GAP"):
            scene_type = "flow"
            priority = "P2"  # GAP场景默认P2
        else:
            # 从s1_index获取原场景信息
            orig_scene = None
            for s in s1_index.get("scenario_index", []):
                if s.get("id") == scene_id:
                    orig_scene = s
                    break
            scene_type = orig_scene.get("type", "flow") if orig_scene else "flow"
            priority = orig_scene.get("priority", "P1") if orig_scene else "P1"

        scenario_index.append({
            "id": scene_id,
            "name": f"富化场景-{scene_id}",
            "type": scene_type,
            "priority": priority,
            "fp_refs": [],  # 从具体场景文件获取
            "file": f"s3a_enriched/{scene_id}.json",
            "enriched_stats": all_stats.get(scene_id, {})
        })

    # 构建function_points（基于fp_mapping）
    enriched_fps = []
    for fp in s1_index.get("function_points", []):
        fp_id = fp.get("id")
        mapping_entry = None
        for m in fp_mapping.get("fp_mapping", []):
            if m.get("fp_id") == fp_id:
                mapping_entry = m
                break

        enriched_fp = {
            "id": fp_id,
            "name": fp.get("name"),
            "entry": fp.get("entry"),
            "priority": fp.get("priority"),
            "constraints": fp.get("constraints", []),
            "source_ids": fp.get("source_ids", []),
            "code_entry": mapping_entry.get("code_entry") if mapping_entry else None,
            "gap_status": mapping_entry.get("status") if mapping_entry else None
        }
        enriched_fps.append(enriched_fp)

    # 构建索引
    enriched_index = {
        "meta": {
            "source": s1_index.get("meta", {}).get("source", "requirement"),
            "doc_path": s1_index.get("meta", {}).get("doc_path", ""),
            "module_role": fp_mapping.get("module_role", "独立功能")
        },
        "function_points": enriched_fps,
        "scenario_index": scenario_index,
        "fp_mapping": fp_mapping.get("fp_mapping", []),
        "gap_summary": fp_mapping.get("gap_summary", {})
    }

    return enriched_index


def main():
    import argparse
    parser = argparse.ArgumentParser(description="合并富化场景")
    parser.add_argument("--output-dir", required=True, help="输出目录")
    args = parser.parse_args()

    output_dir = args.output_dir
    state_dir = os.path.join(output_dir, ".state")

    # 1. 加载输入文件
    s1_index_path = os.path.join(state_dir, "s1_index.json")
    fp_mapping_path = os.path.join(state_dir, "fp_mapping.json")

    if not os.path.exists(s1_index_path):
        print(f"错误: s1_index.json 不存在")
        return 1

    s1_index = load_json(s1_index_path)

    # 优先从stage_summary.json读取module_role（阶段2代码分析的判断结果）
    stage_summary_path = os.path.join(state_dir, "stage_summary.json")
    module_role_from_stage = "独立功能"  # 默认值
    if os.path.exists(stage_summary_path):
        stage_summary = load_json(stage_summary_path)
        module_role_from_stage = stage_summary.get("module_role", "独立功能")

    # fp_mapping可能不存在（兼容旧模式）
    fp_mapping = {"fp_mapping": [], "gap_summary": {}}
    if os.path.exists(fp_mapping_path):
        fp_mapping = load_json(fp_mapping_path)

    # module_role优先级：fp_mapping.json > stage_summary.json > 默认值
    # fp_mapping.json来自阶段3a-gap的富化结果，优先级最高
    if "module_role" in fp_mapping:
        module_role = fp_mapping["module_role"]
    else:
        module_role = module_role_from_stage
    fp_mapping["module_role"] = module_role

    # 2. 加载批次摘要
    batch_summaries = glob_batch_summaries(output_dir)

    if not batch_summaries:
        # 兼容旧模式：如果没有批次摘要，直接从s3a_enriched目录扫描
        print("未找到批次摘要，使用兼容模式扫描s3a_enriched目录")
        enriched_dir = Path(state_dir) / "s3a_enriched"
        if enriched_dir.exists():
            scene_files = sorted(enriched_dir.glob("FS-*.json"))
            batch_summaries = [{
                "batch_id": "legacy",
                "scene_ids": [f.stem for f in scene_files],
                "gap_ids": [f.stem for f in scene_files if f.stem.startswith("FS-GAP")],
                "enriched_stats": {},
                "total_branches_added": 0
            }]

    print(f"发现批次摘要: {len(batch_summaries)}")

    # 3. 构建索引
    enriched_index = build_enriched_index(s1_index, fp_mapping, batch_summaries, output_dir)

    # 4. 写入输出
    output_path = os.path.join(state_dir, "s3a_enriched_index.json")
    save_json(output_path, enriched_index)

    print(f"输出: {output_path}")

    # 5. 统计摘要
    total_scenes = len(enriched_index.get("scenario_index", []))
    total_fps = len(enriched_index.get("function_points", []))

    matched = sum(1 for m in fp_mapping.get("fp_mapping", []) if m.get("status") == "matched")
    not_found = sum(1 for m in fp_mapping.get("fp_mapping", []) if m.get("status") == "not_found")
    code_only = sum(1 for m in fp_mapping.get("fp_mapping", []) if m.get("status") == "code_only")

    print(f"\n## S3a-merge完成摘要")
    print(f"| 项目 | 结果 |")
    print(f"|------|------|")
    print(f"| 场景数 | {total_scenes} |")
    print(f"| FP数 | {total_fps} |")
    print(f"| FP映射 | matched {matched} / not_found {not_found} / code_only {code_only} |")

    return 0


if __name__ == "__main__":
    sys.exit(main())