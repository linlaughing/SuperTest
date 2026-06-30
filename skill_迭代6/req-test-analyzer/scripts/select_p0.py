#!/usr/bin/env python3
"""
select_p0.py - 阶段4-prep：P0筛选 + 门禁脚本生成

从 test_design.json 筛选P0用例，生成 p0_selection.json 和 validate_test.py。
替代原 Agent 方式，执行时间 <1s。

用法：
    python select_p0.py --output-dir <dir> [--p0-count N]
"""

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

# ============================================================
# 门禁脚本模板
# ============================================================

VALIDATE_TEMPLATE = '''"""
validate_test.py - 门禁脚本（阶段4预备）
自动检测测试代码是否符合规范。

三层门禁规则：
  第一层 - 通用禁止项
  第二层 - 模块特定禁止项（从 stage_summary.json 提取）
  第三层 - 通用必须项（此阶段为空列表）
"""

import ast
import sys
from pathlib import Path

# ============================================================
# 第一层 - 通用禁止项
# ============================================================

# 禁止 import 框架内部处理器
FORBIDDEN_IMPORTS = {forbidden_imports}

# 禁止调用私有方法（_xxx 前缀）的正则模式
FORBIDDEN_PRIVATE_PATTERNS = {forbidden_private_patterns}

# 禁止 patch() 替换被测框架类
FORBIDDEN_PATCH_TARGETS = {forbidden_patch_targets}

# 禁止 MagicMock(spec=框架核心类)
FORBIDDEN_MOCK_SPEC_CLASSES = {forbidden_mock_spec_classes}


# ============================================================
# 第二层 - 模块特定禁止项（从 cd_list 提取）
# ============================================================

# 内部处理器类名（禁止直接 import 或实例化）
MODULE_FORBIDDEN_IMPORTS = {module_forbidden_imports}

# 内部方法列表（禁止直接调用）
MODULE_FORBIDDEN_PRIVATE_CALLS = {module_forbidden_private_calls}


# ============================================================
# 第三层 - 通用必须项（此阶段为空列表）
# ============================================================

REQUIRED_IMPORTS: list[str] = []
REQUIRED_PATTERNS: list[str] = []


# ============================================================
# 第四层 - user_test_entry 专用禁止项（从 forbidden_direct_apis 提取）
# ============================================================

USER_ENTRY_FORBIDDEN_APIS = {user_entry_forbidden_apis}


# ============================================================
# 检测逻辑
# ============================================================

class TestValidator:
    """测试文件门禁校验器。"""

    def __init__(self, filepath: str):
        self.filepath = Path(filepath)
        self.source = self.filepath.read_text(encoding="utf-8")
        self.violations: list[dict] = []

    def validate(self) -> bool:
        """执行所有校验规则，返回 True 表示通过。"""
        self._check_forbidden_imports()
        self._check_forbidden_private_calls()
        self._check_forbidden_patch()
        self._check_forbidden_mock_spec()
        self._check_user_entry_forbidden_apis()
        return len(self.violations) == 0

    def _check_forbidden_imports(self):
        """第一层：禁止 import 框架内部处理器。"""
        all_forbidden = set(FORBIDDEN_IMPORTS + MODULE_FORBIDDEN_IMPORTS)
        for lineno, line in enumerate(self.source.splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            for name in all_forbidden:
                # 匹配 import xxx 或 from xxx import xxx
                if f"import {{name}}" in stripped or f"from.*import.*{{name}}" in stripped:
                    self.violations.append({{
                        "layer": 1,
                        "rule": "FORBIDDEN_IMPORT",
                        "lineno": lineno,
                        "detail": f"禁止 import 框架内部处理器: {{name}}",
                    }})

    def _check_forbidden_private_calls(self):
        """第一层 + 第二层：禁止调用私有方法。"""
        import re
        all_patterns = FORBIDDEN_PRIVATE_PATTERNS + [
            rf"\\.{{method}}\\b" for method in MODULE_FORBIDDEN_PRIVATE_CALLS
        ]
        for lineno, line in enumerate(self.source.splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            for pattern in all_patterns:
                if re.search(pattern, stripped):
                    method_name = pattern.replace(r"\\.", ".").replace(r"\\b", "")
                    self.violations.append({{
                        "layer": 2,
                        "rule": "FORBIDDEN_PRIVATE_CALL",
                        "lineno": lineno,
                        "detail": f"禁止调用内部私有方法: {{method_name}}",
                    }})
                    break  # 每行只报一次

    def _check_forbidden_patch(self):
        """第一层：禁止 patch() 替换被测框架类。"""
        for lineno, line in enumerate(self.source.splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if "patch(" in stripped or "patch.object(" in stripped:
                for target in FORBIDDEN_PATCH_TARGETS:
                    if target in stripped:
                        self.violations.append({{
                            "layer": 1,
                            "rule": "FORBIDDEN_PATCH",
                            "lineno": lineno,
                            "detail": f"禁止 patch() 替换被测框架类: {{target}}",
                        }})

    def _check_forbidden_mock_spec(self):
        """第一层：禁止 MagicMock(spec=框架核心类)。"""
        for lineno, line in enumerate(self.source.splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if "MagicMock" in stripped or "Mock(" in stripped:
                for cls in FORBIDDEN_MOCK_SPEC_CLASSES:
                    if f"spec={{cls}}" in stripped or f"spec = {{cls}}" in stripped:
                        self.violations.append({{
                            "layer": 1,
                            "rule": "FORBIDDEN_MOCK_SPEC",
                            "lineno": lineno,
                            "detail": f"禁止 MagicMock(spec=框架核心类): {{cls}}",
                        }})

    def _check_user_entry_forbidden_apis(self):
        """第四层：user_test_entry 专用禁止项。"""
        if not USER_ENTRY_FORBIDDEN_APIS:
            return
        for lineno, line in enumerate(self.source.splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            for api in USER_ENTRY_FORBIDDEN_APIS:
                if api in stripped:
                    self.violations.append({{
                        "layer": 4,
                        "rule": "USER_ENTRY_FORBIDDEN_API",
                        "lineno": lineno,
                        "detail": f"禁止使用内部API（支持性组件应通过用户入口测试）: {{api}}",
                    }})

    def report(self):
        """输出校验报告。"""
        if not self.violations:
            print(f"[PASS] {{self.filepath}} - 所有门禁规则通过")
            return

        print(f"[FAIL] {{self.filepath}} - 发现 {{len(self.violations)}} 个违规:")
        for v in self.violations:
            print(f"  L{{v['layer']}} | {{v['rule']}} | 行{{v['lineno']}} | {{v['detail']}}")


def main():
    """命令行入口：python validate_test.py <test_file.py>"""
    if len(sys.argv) < 2:
        print("用法: python validate_test.py <test_file.py> [test_file2.py ...]")
        sys.exit(1)

    all_passed = True
    for filepath in sys.argv[1:]:
        validator = TestValidator(filepath)
        passed = validator.validate()
        validator.report()
        if not passed:
            all_passed = False

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
'''


def load_json(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: str, data, indent=2):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=indent)


def select_p0_cases(cases: list[dict], p0_count: int) -> list[dict]:
    """筛选P0用例：按 test_type 分组，每组选1个，优先正常E2E。

    算法：
    1. 只从 priority="P0" 的用例中选
    2. 按 test_type 分组，优先级：正常E2E > 异常E2E > 其他
    3. 每组取 case_id 最小的（最早定义的用例）
    4. P0用例不足 p0_count 时，从非P0用例中按 test_type 多样性补充
    """
    type_order = ["正常E2E", "异常E2E", "变体E2E", "边界E2E", "约束E2E", "质量E2E"]

    p0_pool = [c for c in cases if c.get("priority") == "P0"]
    by_type = defaultdict(list)
    for c in p0_pool:
        by_type[c.get("test_type", "")].append(c)
    # 每组按 case_id 排序
    for t in by_type:
        by_type[t].sort(key=lambda c: c["case_id"])

    selected = []
    seen_ids = set()

    # 按优先级遍历类型，每组取1个
    for t in type_order:
        if len(selected) >= p0_count:
            break
        group = by_type.get(t, [])
        for c in group:
            if c["case_id"] not in seen_ids:
                selected.append(c)
                seen_ids.add(c["case_id"])
                break

    # P0用例不足时，从全部用例按 test_type 补充
    if len(selected) < p0_count:
        all_by_type = defaultdict(list)
        for c in cases:
            if c["case_id"] not in seen_ids:
                all_by_type[c.get("test_type", "")].append(c)
        for t in type_order:
            if len(selected) >= p0_count:
                break
            group = all_by_type.get(t, [])
            if group:
                selected.append(group[0])
                seen_ids.add(group[0]["case_id"])

    return selected[:p0_count]


def match_p0_ref(case: dict, p0_cases: list[dict]) -> str:
    """为用例匹配最相关的P0参考用例。优先同 test_type，其次任意P0。"""
    same_type = [p for p in p0_cases if p.get("test_type") == case.get("test_type")]
    if same_type:
        return same_type[0]["case_id"]
    # 优先正常E2E
    normal = [p for p in p0_cases if p.get("test_type") == "正常E2E"]
    if normal:
        return normal[0]["case_id"]
    return p0_cases[0]["case_id"] if p0_cases else ""


def extract_forbidden_names(stage_summary: dict) -> dict:
    """从 stage_summary.json 提取门禁禁止项。"""
    cd_list = stage_summary.get("cd_list", [])
    module_imports = set()
    module_methods = set()

    for cd in cd_list:
        loc = cd.get("location", "")
        # 从 location 提取类名（文件名中的类部分）
        # e.g. "message_summary_offloader.py:723" -> MessageSummaryOffloader
        filename = loc.split(":")[0].split("/")[-1] if loc else ""
        if filename.endswith(".py"):
            # snake_case -> CamelCase
            parts = filename[:-3].split("_")
            class_name = "".join(p.capitalize() for p in parts)
            module_imports.add(class_name)

        # 从 desc 提取方法名（_xxx 模式）
        desc = cd.get("desc", "")
        for match in re.finditer(r"\b(_\w+)\b", desc):
            name = match.group(1)
            if name.startswith("__"):
                continue
            module_methods.add(name)

    # 从 user_test_entry.forbidden_direct_apis 提取禁止的内部 API
    user_entry = stage_summary.get("user_test_entry")
    if user_entry:
        for api in user_entry.get("forbidden_direct_apis", []):
            # "ContextEngine.create_context" → class=ContextEngine, method=create_context
            # "context.add_messages" → class=context, method=add_messages
            if "." in api:
                parts = api.rsplit(".", 1)
                module_imports.add(parts[0])
                module_methods.add(parts[1])
            else:
                module_imports.add(api)

    return {
        "module_imports": sorted(module_imports),
        "module_methods": sorted(module_methods),
    }


def generate_validate_script(forbidden: dict, user_entry_apis: list[str] | None = None) -> str:
    """生成 validate_test.py 内容。"""
    names = forbidden["module_imports"]
    methods = forbidden["module_methods"]

    # 第一层：通用禁止项 = 模块类名
    forbidden_imports = json.dumps(names, ensure_ascii=False)
    forbidden_private = json.dumps([rf"\.{m}\b" for m in methods], ensure_ascii=False)
    forbidden_patch = json.dumps(names, ensure_ascii=False)
    forbidden_mock = json.dumps(names, ensure_ascii=False)

    # 第二层：模块特定 = 同上
    module_imports = json.dumps(names, ensure_ascii=False)
    module_methods = json.dumps(methods, ensure_ascii=False)

    # 第四层：user_test_entry 专用禁止项
    user_entry_apis_json = json.dumps(user_entry_apis or [], ensure_ascii=False)

    return VALIDATE_TEMPLATE.format(
        forbidden_imports=forbidden_imports,
        forbidden_private_patterns=forbidden_private,
        forbidden_patch_targets=forbidden_patch,
        forbidden_mock_spec_classes=forbidden_mock,
        module_forbidden_imports=module_imports,
        module_forbidden_private_calls=module_methods,
        user_entry_forbidden_apis=user_entry_apis_json,
    )


def build_defect_hints(
    cases: list[dict], state_dir: str
) -> dict:
    """构建缺陷线索文件：case_id → 相关缺陷/异常/约束。

    匹配链：case.source_scene → fp_refs → code_entry → exception_catalog/constraint_catalog
    """
    # 读取 s3a_enriched_index（FP→code_entry映射）
    enriched_path = os.path.join(state_dir, "s3a_enriched_index.json")
    if not os.path.exists(enriched_path):
        return {}
    enriched = load_json(enriched_path)

    # FP id → code_entry 映射
    fp_to_entry: dict[str, str] = {}
    for fp in enriched.get("function_points", []):
        entry = fp.get("code_entry", "")
        if entry:
            fp_to_entry[fp["id"]] = entry

    # scenario id → fp_refs 映射
    scene_to_fps: dict[str, list[str]] = {}
    for si in enriched.get("scenario_index", []):
        scene_to_fps[si["id"]] = si.get("fp_refs", [])

    # 读取 s2_code_facts（异常目录+约束目录+缺陷清单）
    facts_path = os.path.join(state_dir, "s2_code_facts.json")
    if not os.path.exists(facts_path):
        return {}
    facts = load_json(facts_path)

    # entry → 相关异常（从 reachable_from 匹配）
    entry_exceptions: dict[str, list[str]] = defaultdict(list)
    for exc in facts.get("exception_catalog", []):
        for entry in exc.get("reachable_from", []):
            # 精简格式："异常类型: 触发条件"
            hint = f"{exc['exception_type']}: {exc.get('trigger_condition', '')}"
            entry_exceptions[entry].append(hint)

    # entry → 相关约束（从 target 匹配）
    entry_constraints: dict[str, list[str]] = defaultdict(list)
    for con in facts.get("constraint_catalog", []):
        target = con.get("target", "")
        hint = f"{con.get('rule', '')}，触发条件: {con.get('trigger', '')}"
        entry_constraints[target].append(hint)

    # 全局缺陷清单（severity ≥ 中）
    code_defects = [
        {"id": cd["id"], "desc": cd["desc"], "severity": cd["severity"]}
        for cd in facts.get("code_defects", [])
        if cd.get("severity", "低") in ("高", "中")
    ]

    # source_file → 相关入口（用于将CD关联到entry）
    file_to_entries: dict[str, set[str]] = defaultdict(set)
    for ec in facts.get("entry_catalog", []):
        sf = ec.get("source_file", "")
        if sf:
            entry_key = f"{ec['class']}.{ec['method']}"
            file_to_entries[sf].add(entry_key)
    # entry → 关联的CD id列表
    entry_defect_ids: dict[str, list[str]] = defaultdict(list)
    for cd in facts.get("code_defects", []):
        if cd.get("severity", "低") not in ("高", "中"):
            continue
        loc = cd.get("location", "")
        cd_file = loc.split(":")[0] if loc else ""
        for entry_key in file_to_entries.get(cd_file, set()):
            entry_defect_ids[entry_key].append(cd["id"])

    # 为每个 case 构建线索
    case_hints: dict[str, dict] = {}
    for case in cases:
        cid = case["case_id"]
        source_scene = case.get("source_scene", "")
        fp_refs = scene_to_fps.get(source_scene, [])
        # 收集该 case 涉及的所有 code_entry
        entries = list({fp_to_entry[fp] for fp in fp_refs if fp in fp_to_entry})
        if not entries:
            continue
        # 聚合相关异常、约束和缺陷ID
        rel_exc: list[str] = []
        rel_con: list[str] = []
        rel_cd_ids: list[str] = []
        for entry in entries:
            rel_exc.extend(entry_exceptions.get(entry, []))
            rel_con.extend(entry_constraints.get(entry, []))
            rel_cd_ids.extend(entry_defect_ids.get(entry, []))
        # 去重
        rel_cd_ids = list(dict.fromkeys(rel_cd_ids))
        # 只记录有内容的 case
        if rel_exc or rel_con or rel_cd_ids:
            case_hints[cid] = {
                "entries": entries,
                "relevant_exceptions": rel_exc[:5],
                "relevant_constraints": rel_con[:5],
                "relevant_defect_ids": rel_cd_ids[:5],
            }

    return {"code_defects": code_defects, "case_hints": case_hints}


def main():
    parser = argparse.ArgumentParser(description="P0筛选 + 门禁脚本生成")
    parser.add_argument("--output-dir", required=True, help="输出目录")
    parser.add_argument("--p0-count", type=int, default=3, help="P0用例数量")
    args = parser.parse_args()

    output_dir = args.output_dir
    state_dir = os.path.join(output_dir, ".state")

    # 读取输入
    cases = load_json(os.path.join(output_dir, "test_design.json"))
    stage_summary = load_json(os.path.join(state_dir, "stage_summary.json"))

    # P0筛选
    p0_cases = select_p0_cases(cases, args.p0_count)
    p0_ids = {c["case_id"] for c in p0_cases}

    # 剩余用例 + p0_ref_match
    remaining = []
    for c in cases:
        if c["case_id"] not in p0_ids:
            c_copy = dict(c)
            c_copy["p0_ref_match"] = match_p0_ref(c, p0_cases)
            remaining.append(c_copy)

    # 写入 p0_selection.json
    p0_selection = {
        "p0_cases": p0_cases,
        "remaining_cases": remaining,
        "stats": {
            "total": len(cases),
            "p0_count": len(p0_cases),
            "remaining_count": len(remaining),
        },
    }
    save_json(os.path.join(state_dir, "p0_selection.json"), p0_selection)

    # 生成 validate_test.py
    forbidden = extract_forbidden_names(stage_summary)
    # 从 user_test_entry 提取禁止的内部 API 列表
    user_entry = stage_summary.get("user_test_entry")
    user_entry_apis = user_entry.get("forbidden_direct_apis", []) if user_entry else None
    script_content = generate_validate_script(forbidden, user_entry_apis)
    validate_path = os.path.join(state_dir, "validate_test.py")
    with open(validate_path, "w", encoding="utf-8") as f:
        f.write(script_content)

    # 生成 defect_hints.json（仅在有有效内容时写入）
    defect_hints = build_defect_hints(cases, state_dir)
    has_content = defect_hints.get("code_defects") or defect_hints.get("case_hints")
    if has_content:
        save_json(os.path.join(state_dir, "defect_hints.json"), defect_hints)
        n_hinted = len(defect_hints.get("case_hints", {}))
        n_cd = len(defect_hints.get("code_defects", []))
        print(f"Defect hints: {n_hinted} cases, {n_cd} defects")

    # 输出摘要
    type_counts = defaultdict(int)
    for c in p0_cases:
        type_counts[c.get("test_type", "?")] += 1
    type_str = " / ".join(f"{t} {n}" for t, n in sorted(type_counts.items()))

    print(f"P0: {len(p0_cases)} ({type_str})")
    print(f"Remaining: {len(remaining)}")
    print(f"Output: p0_selection.json, validate_test.py")


if __name__ == "__main__":
    main()
