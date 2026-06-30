---
name: req-test-analyzer
description: 需求驱动端到端测试生成器。从需求侧出发生成端到端场景（flow/framework/quality），整合功能点、框架场景和质量维度。触发词："/req-test-analyzer", "需求测试分析", "需求侧测试", "端到端场景生成"
---

# 需求驱动端到端测试生成器

从需求侧出发的端到端测试生成，生成 flow/framework/quality 三类场景，整合业务流程和质量维度。

## 双模式

| 模式 | 触发条件 | 流程 | 输出 |
|------|----------|------|------|
| **标准模式** | 提供 `code_path` / `--pr` / `--commit` 之一 | 0(可选)→1→2→3a→3b→4a→4b→5 | 完整测试代码 + 报告 |
| **纯需求模式** | 以上均未提供 | 1→2R→3aR→3b（终止） | 测试设计文档 |

> 纯需求模式详细说明已内嵌于 `templates/stage2R_req_summary.md` 和 `templates/stage3aR_framework.md`

## 核心流程

```
标准模式：
  ┌─阶段1(S1-Agent)───┐
  │ 需求侧场景分析     │
  │ → s1_index.json   │
  │ → s1_scenarios/*  │
 并│                   │
 行│                   │ → 编排器cp → ┌─阶段3a-gap─┐  → 阶段3b（小文件） → Python merge → 阶段4 → 阶段5
  │                   │              │ GAP场景生成  │
  └─阶段2(S2-Agent)───┘              └─────────────┘
  │ 代码事实扫描       │                     ↕ 并行
  │ → s2_code_facts.json│  ┌─阶段3a-fw──┐
  └───────────────────┘   │ 框架场景补充 │
                          │ → s3a_framework.json │
                          └──────────────┘

纯需求模式：
  阶段1(S1-Agent) → 阶段2R(S2R-Agent) → 阶段3aR(S3aR-Agent) → 阶段3b(终止)
```

## 场景设计原则

**一条用户操作链路 = 一个场景。** 同一链路的配置差异/异常分支不拆独立场景。

| 场景类型 | 来源 | 说明 |
|----------|------|------|
| **flow（流程驱动）** | 主流程 | 每条用户操作链路1个场景，含变体和异常子项 |
| **framework（框架组合）** | 框架场景×FP | 框架场景作为执行环境嵌入用户链路 |
| **quality（质量保障）** | RK/CD/GAP → branches.quality | 作为quality分支附着到已有链路，注入触发条件 |

## 参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `requirement_doc` | 需求文档路径 | **必填** |
| `code_path` | 代码目录 | **可选**（与--pr/--commit三选一，均未提供则纯需求模式） |
| `--framework-scenes` | 框架场景文件 | **必填**（用户提供） |
| `--output-dir` | 输出目录 | `analysis_output/` |
| `--case-batch-size` | 并行Agent数量（阶段4b） | 5 |
| `--p0-count` | P0用例数量（阶段4a） | 3 |
| `--max-fix-attempts` | 最大修复轮数（阶段4b） | 3 |
| `--start-stage` | 从指定阶段开始 | 自动检测 |
| `--pr` | PR编号，逗号分隔 | 可选（与code_path/commit三选一） |
| `--commit` | Commit ID，逗号分隔 | 可选（与code_path/pr三选一） |
| `--base` | 基准分支 | 仓库默认分支 |

**注意**：
- `--framework-scenes` 由用户保证提供，skill 不生成
- 模块角色、入口目录、代码缺陷从阶段2的 `s2_code_facts.json` + `stage_summary.json` 获取
- 代码独有能力(code_only)由阶段3a-gap Agent从 `s2_code_facts.json` 提取并生成GAP场景

## 模块角色分流

| 角色 | 场景类型 | 说明 |
|------|----------|------|
| 独立功能 | flow + framework + quality | 流程场景 + 框架组合 + 质量场景 |
| 支持性组件 | framework + quality | 框架场景组合 + 质量场景 |

## 强制覆盖规则

| 来源类型 | 覆盖规则 |
|----------|----------|
| RK_xxx | **强制全覆盖** |
| CD_xxx（高严重度） | **强制全覆盖** |
| GAP_xxx（P0/P1） | **强制全覆盖** |
| FP_xxx | flow+framework场景全覆盖 |
| 主流程 | 每个主流程有对应场景 |
| 相关框架场景 | 每个相关框架场景有对应场景 |
| 不可验证项 | 标注skip_reason，不生成无意义用例 |

## E2E测试层级约束

**所有E2E测试必须通过用户可见的入口驱动，禁止绕过用户层直接调用内部组件。**

| 规则 | 说明 |
|------|------|
| FP提取聚焦用户入口 | 功能点描述用户可观测行为，入口记录用户触发方式，不提取processor/handler等内部组件 |
| 用例步骤用用户操作语言 | 禁止出现内部组件名（processor/handler/offloader/builder），步骤从用户视角描述 |
| 代码生成禁止内部API | 禁止直接实例化内部组件、调用私有方法(_xxx)、手写内部类Stub |
| 测试入口 | Agent / Runner / Session / Workflow / 公开API / 公开配置 |

---

## 阶段间人工确认

**标记为"人工确认：✅"的阶段完成后，必须使用 `AskUserQuestion` 工具询问用户是否继续。标记为"❌"的阶段自动进入下一阶段。**

```python
AskUserQuestion(questions=[{
    "question": "阶段 X 已完成，是否继续执行阶段 X+1？",
    "header": "阶段确认",
    "options": [
        {"label": "继续", "description": "进入阶段 X+1"},
        {"label": "跳过后续", "description": "不再执行后续阶段，保留当前输出"},
        {"label": "重新执行", "description": "重新执行当前阶段（--start-stage=X）"}
    ],
    "multiSelect": false
}])
```

---

## 编排器原则

**本skill采用纯编排器模式：主Agent（编排器）只做调度，不读业务文件内容。**

| 原则 | 说明 |
|------|------|
| 零知识调度 | 编排器只检查文件存在性、读几KB的progress.json，不读业务文件 |
| 全Agent隔离 | 每个阶段由独立子Agent执行，编排器只收到一行摘要 |
| 后台化高量 | 阶段4a/4b的case级Agent用 `run_in_background=True`，编排器不累积返回 |
| 文件即协议 | 所有数据通过文件传递，Agent间无上下文依赖 |
| 阶段验证后更新 | 验证产出文件存在后，编排器 Write progress.json 更新阶段状态（子Agent不写） |

### 通用子Agent启动模式

对每个阶段，编排器执行：读取模板 → 替换参数 → spawn Agent → 验证输出 → 进入下一阶段。

```
1. Read templates/stage*_*.md → 替换参数得到 prompt
2. Agent(prompt=填充后prompt, description="阶段X", [run_in_background=True])
3. 验证输出文件存在（不读内容）
4. 如需人工确认 → AskUserQuestion
```

---

## 执行流程

### 阶段1+2：并行启动（标准模式）

> 人工确认：❌ | 模式：标准

**调度顺序**：

```
步骤1: 并行启动（run_in_background=True）
  → Agent-S1（需求侧场景分析）
    模板: templates/stage1_req_analyze.md
    参数: {skill_dir} {output_dir} {requirement_doc} {work_dir}
    输出: .state/s1_index.json + .state/s1_scenarios/FS-*.json + requirement_analysis.md（摘要）
    子Agent内部读取 shared/scenario_schema.md

  → Agent-S2（代码事实扫描）
    模板: templates/stage2_code_scan.md
    参数: {skill_dir} {output_dir} {code_path}
    输出: .state/s2_code_facts.json（代码事实JSON）+ .state/stage_summary.json（简化版）
    ⚠️ 不读取需求侧任何文件，不生成场景

  → 等待全部完成，验证文件存在

步骤1.5: 支持性组件门禁（编排器内联执行）
  → Read .state/stage_summary.json（仅读 module_role 和 user_test_entry 字段）
  → if module_role == "支持性组件" 且 user_test_entry 字段不存在:
      → AskUserQuestion: "阶段2判定模块为支持性组件但未识别用户层入口。请选择：① 补做入口追溯(重跑阶段2) ② 手动提供入口信息后继续 ③ 忽略，使用内部API继续"
  → if user_test_entry 存在且 confidence == null:
      → 输出警告："用户入口置信度为null，阶段4a将按最低约束处理"
  → 放行后进入步骤2

步骤2: 自动进入阶段3a（GAP场景+框架补充）
```

### 阶段1：需求侧场景分析（纯需求模式，子Agent执行）

> 人工确认：❌ | 条件：纯需求模式

- 模板：`templates/stage1_req_analyze.md`
- 参数：`{skill_dir}` `{output_dir}` `{requirement_doc}` `{work_dir}`
- 验证：`.state/s1_index.json` 存在且含 function_points + scenario_index；`.state/s1_scenarios/` 目录下有对应场景文件
- 完成后自动进入阶段2R

### 阶段2R：需求侧摘要（纯需求模式，子Agent执行）

> 人工确认：❌ | 条件：纯需求模式

- 模板：`templates/stage2R_req_summary.md`
- 参数：`{skill_dir}` `{output_dir}`
- 输入：`.state/s1_index.json`（S1场景索引，直接提取统计）
- 输出：`.state/stage_summary.json`（简化版：module_role=独立功能 + cd_list=[]）
- 验证：`stage_summary.json` 存在且 `mode=requirement_only`
- 完成后自动进入阶段3aR

### 阶段3a：GAP场景 + 框架补充（标准模式）

> 人工确认：❌ | 条件：标准模式
> **设计原则**：S1场景直接复用（无需富化），仅补充代码独有能力(GAP)和框架场景。

**调度顺序**：

```
步骤1: 编排器内联操作（不启动Agent）
  → Bash mkdir -p .state/s3a_enriched/ && cp .state/s1_scenarios/*.json .state/s3a_enriched/（直接复制S1场景）

步骤2: 2-Agent并行启动（run_in_background=True）
  → Agent-S3a-gap（GAP场景生成）
    模板: templates/stage3a_gap.md
    参数: {skill_dir} {output_dir}
    输入: .state/s1_index.json + .state/s2_code_facts.json
    输出: .state/s3a_enriched/FS-GAP-*.json

  → Agent-S3a-fw（框架场景补充）
    模板: templates/stage3a_framework.md
    参数: {skill_dir} {output_dir} {framework_scenes}
    输入: .state/s1_index.json + framework_scenes + .state/stage_summary.json
    输出: .state/s3a_framework.json
    ⚠️ 不读取 s2_code_facts.json
    ⚡ 第三步标注组件类型，第五步消费标注触发组合追问

  → 等待全部完成，验证文件存在

步骤3: Python合并脚本（前景，<1秒）
  → 执行: python scripts/merge_enriched.py
  → 输入: 扫描 .state/s3a_enriched/ 目录 + s1_index.json
  → 输出: .state/s3a_enriched_index.json

自动进入阶段3b
```

> **简化说明**：S1已从需求侧提取完整的6类分支（parameter/boundary/exception/quality/constraint/cross），代码侧exception富化在3b被截断率>80%，CD缺陷直接从stage_summary.json→4-prep门禁，无需经过3a-code转quality分支。

### 阶段3aR：框架场景补充（纯需求模式，子Agent执行）

> 人工确认：❌ | 条件：纯需求模式

- 模板：`templates/stage3aR_framework.md`
- 参数：`{skill_dir}` `{output_dir}` `{framework_scenes}`
- 输入：`.state/s1_index.json` + `stage_summary.json` + framework-scenes
- 执行：S1场景直接复用（无需去重/生成），仅做框架场景相关性判断和补充
- 输出：`e2e_scenes.json` + `e2e_scenes.md`
- 验证：`e2e_scenes.json` 存在且含 flow_scenarios
- 完成后进入阶段3b

### 阶段3b：测试用例设计（小文件模式，N-Agent + Python merge）

> 人工确认：✅（3b完成后强制确认，提示用户检查并修改 `test_design.json`）

**调度顺序**：

```
步骤1: 编排器读取索引（零知识调度）
  → Read .state/s3a_enriched_index.json 获取 scenario_index（只读id列表）
  → Read .state/s3a_framework.json 获取 framework_scenarios 数量
  → 计算批次分配：flow场景 + framework场景按batch_size分批

步骤2: 并行启动Batch Agent（run_in_background=True）
  → Agent-S3b-batch-N（按场景ID分配，每批≤batch_size）
    模板: templates/stage3b_batch_design.md
    参数: {skill_dir} {output_dir} {scene_ids} {next_seq}
    输入: 按需Read单场景文件（.state/s3a_enriched/FS-*.json 或从s3a_framework.json提取）
    输出: test_design_batch_N.json
    ⚠️ 禁止读取大JSON文件，只Read索引和单场景文件

  → 等待全部完成

步骤3: Python merge脚本（前景执行）
  → 执行: python scripts/merge_test_design.py
  → 输入: test_design_batch_*.json + .state/s3a_enriched/*.json + .state/s3a_framework.json
  → 输出: test_design.json + scene_tc_mapping.json + e2e_scenes.json（可选）
  → 验证: 三个文件均存在
```

> **小文件模式**：每个Batch Agent只Read索引(~5KB) + 按需单场景文件(~15KB)，避免读取大JSON。
> **纯需求模式终止点**：阶段3b完成后终止，不执行后续阶段，输出终止提示：

```
## 纯需求模式完成

已生成测试设计文档：
├── requirement_analysis.md     # 需求分析
├── .state/stage_summary.json   # 需求侧摘要（简化版）
├── e2e_scenes.md               # 端到端场景
├── e2e_scenes.json             # 结构化场景数据
├── test_design.json            # 测试用例设计
└── scene_tc_mapping.json       # 场景-用例映射

后续阶段（代码生成、验证、报告）需要代码输入。
如需继续生成测试代码，请提供 code_path 后重新执行。
```

### 阶段4：端到端自动化测试代码生成与验证（多-Agent编排）

> 人工确认：✅（4a完成后确认P0，4b完成后确认）
> **用户保证**：ai_reference/framework_reference.md 和 test_common_template.md 必定存在
> **核心原则**：4a先行P0验证产出金标准 → 4b参考P0批量生成 → 测试目的是**发现SDK缺陷**

**调度顺序**：

```
步骤1: Python脚本（前景，<1s）
  → 执行: python {skill_dir}/scripts/select_p0.py --output-dir {output_dir} --p0-count {p0_count}
  → 输入: test_design.json + .state/stage_summary.json
  → 输出: .state/p0_selection.json + .state/validate_test.py
  → 验证: 两个文件均存在

步骤2: 4a P0深度验证（max 2并发，run_in_background=True）
  → 读取 p0_selection.json 的 p0_cases 数组
  → 对每个P0用例：
    模板: templates/stage4a_p0_verify.md（已有）
    参数: {case_id} {case_name} {steps} {expected} {output_dir} {work_dir} {validate_script}
    如 {output_dir}/.state/skeleton/ 存在，在模板reference_files首位加入skeleton文件
    输出: test_{case_id}.py + .state/results/{case_id}.json
  → 滑动窗口（max 2并发），每完成1个立即检查结果文件存在

步骤3: P0质量抽检（编排器轻量执行）
  → 对每个P0用例读取 .state/results/{case_id}.json（只读 status/mock_file/aw_classes_used 字段）
  → 抽检项：mock文件存在 | aw_classes_used 非空 | 断言≥L2
  → 不通过则修复后重新验证
  → 人工确认P0用例质量

步骤4: 4b 批量生成（滑动窗口 max batch_size 并发，run_in_background=True）
  → 读取 p0_selection.json 的 remaining_cases 数组
  → 对每个剩余用例：
    模板: templates/stage4b_batch_gen.md（已有）
    参数: {case_id} {case_name} {steps} {expected} {output_dir} {work_dir}
          {validate_script} {reference_case_file} {reference_mock_file}
    如 {output_dir}/.state/skeleton/ 存在，在模板reference_files首位加入skeleton文件
    输出: test_{case_id}.py + .state/results/{case_id}.json
  → 滑动窗口：完成1个立即补1个，并发池始终满载
  → 编排器只维护 running 字典（不累积agent输出内容）

步骤5: Python脚本（前景，<1s）
  → 执行: python {skill_dir}/scripts/aggregate_results.py --output-dir {output_dir}
  → 输入: .state/results/*.json
  → 输出: case_results.json
  → 验证: case_results.json 存在
```

> **Prompt大小限制（4a/4b强制）**：传递给子Agent的内容 <5KB。
> 禁止传递：test_design.json全文、requirement_analysis.md、code_analysis.md
> 只传递：case_id + name + steps + expected + 参考路径 + output_dir + work_dir

### 阶段5：测试报告生成（子Agent执行）

> 人工确认：❌（最终输出）

- 模板：`templates/stage5_report.md`
- 参数：`{skill_dir}` `{output_dir}`
- 验证：`report.md` 存在
- 子Agent内部读取共享参考文件执行

---

## 输出文件

### 标准模式

```
{output_dir}/
├── requirement_analysis.md       # 阶段1（摘要）
├── code_analysis.md              # 阶段2（摘要）
├── test_design.json              # 阶段3b（Python merge生成）
├── scene_tc_mapping.json         # 阶段3b
├── case_results.json             # 阶段4
├── test_{case_id}.py             # 阶段4
├── report.md                     # 阶段5
└── .state/
    ├── skeleton/                  # 阶段1（文档代码示例，可选）
    ├── progress.json
    ├── s1_index.json              # 阶段1（轻量索引：FP清单 + scenario_index）
    ├── s1_scenarios/              # 阶段1（逐场景文件）
    │   ├── FS-001.json
    │   └── ...
    ├── s2_code_facts.json         # 阶段2（代码事实：5目录，exception含reachable_from）
    ├── s3a_enriched_index.json    # 阶段3a（合并索引：S1场景 + GAP + 统计）
    ├── s3a_enriched/              # 阶段3a（S1场景复制 + GAP场景）
    │   ├── FS-001.json
    │   ├── FS-GAP-001.json
    │   └── ...
    ├── s3a_framework.json         # 阶段3a-fw（框架场景）
    ├── stage_summary.json         # 阶段2（简化版：module_role + cd_list）
    ├── p0_selection.json          # 阶段4-prep（P0筛选结果）
    ├── validate_test.py           # 阶段4-prep（门禁脚本）
    └── results/                   # 阶段4
        └── {case_id}.json
```

> **e2e_scenes.json可选生成**：阶段3b Python merge脚本可选输出，用于后续阶段参考。

### 纯需求模式

```
{output_dir}/
├── requirement_analysis.md       # 阶段1（摘要）
├── e2e_scenes.md                 # 阶段3aR
├── e2e_scenes.json               # 阶段3aR（结构化）
├── test_design.json              # 阶段3b
├── scene_tc_mapping.json         # 阶段3b
└── .state/
    ├── progress.json
    ├── s1_index.json              # 阶段1（轻量索引）
    ├── s1_scenarios/              # 阶段1（逐场景文件）
    └── stage_summary.json        # 阶段2R（简化版：module_role + cd_list）
```

---

## 文件结构

```
req-test-analyzer/
├── skill.md                              # 主入口（编排器调度表）
├── scripts/
│   ├── merge_enriched.py                 # 阶段3a 场景合并脚本（S1复制+GAP合并）
│   ├── merge_test_design.py              # 阶段3b 用例合并脚本
│   ├── select_p0.py                      # 阶段4-prep P0筛选+门禁脚本生成
│   └── aggregate_results.py              # 阶段4-agg 结果聚合
├── shared/
│   ├── scenario_schema.md                # 场景JSON schema（索引+单场景+code_facts）
│   └── code_analysis_template.md         # 代码分析输出格式（阶段2）
└── templates/
    ├── stage1_req_analyze.md             # 阶段1 子Agent Prompt
    ├── stage2_code_scan.md        # 阶段2 子Agent Prompt（代码事实扫描）
    ├── stage2R_req_summary.md       # 阶段2R 子Agent Prompt
    ├── stage3a_gap.md         # 阶段3a-gap 子Agent Prompt（GAP场景生成）
    ├── stage3a_framework.md    # 阶段3a 子Agent Prompt（框架场景补充）
    ├── stage3aR_framework.md      # 阶段3aR 子Agent Prompt（简化场景）
    ├── stage3b_batch_design.md        # 阶段3b 批次 子Agent Prompt（小文件模式）
    ├── stage4a_p0_verify.md       # 阶段4a 子Agent Prompt（P0深度验证）
    ├── stage4b_batch_gen.md       # 阶段4b 子Agent Prompt（批量生成）
    └── stage5_report.md        # 阶段5 子Agent Prompt（报告生成）
```

---

## 用户目录文件约定

用户需在测试目录下提供 `ai_reference/`：

```
{work_dir}/ai_reference/
├── test_common_template.md     # 必须提供：通用测试模板
├── framework_reference.md      # 必须提供：框架可复用资产
└── test_req_template.md        # 可选：需求特定模板
```

---

## 关键检查项（各阶段详细验证已内嵌于对应子Agent模板中）

- 阶段1：禁止查看代码 | FP三原则（单入口/单行为/可验证）+ 合并拆分规则 | cross分支≤5 | 拆分文件产出 | FP清单 + flow_scenarios含steps和6类分支
- 阶段2：s2_code_facts.json 含5目录 + stage_summary.json含module_role | 入口仅编录公开API | 异常三级漏斗过滤+reachable_from | 无内部组件
- 阶段3a-fpmap：~~已删除，批次分配由编排器内联计算~~
- 阶段3a：2-Agent并行（gap∥fw）| S1场景直接复制 | GAP从code_only生成 | 框架场景强制覆盖
- 阶段2R：stage_summary.json 含 `mode: "requirement_only"` + `module_role: "独立功能"` + `cd_list: []`
- 阶段3aR：S1场景直接复用 | 仅框架场景补充 | 无去重/GAP
- 阶段3b：小文件模式（禁止读取大JSON）| 截断优先级规则（隐含异常>显式、行为差异>值域差异）| 链路完整性（每个用例含完整steps）| Python merge聚合 | 步骤无技术术语 | 预期结果≥2维度
- 阶段4a：辅助类优先使用 | Mock响应文件已创建 | 入口合法性验证通过 | 用户评审通过
- 阶段4b：参考P0范例 | Mock响应文件已创建 | 门禁验证通过 | 断言≥L1且≥2维度
- 阶段5：report.md 含 CD清单 + GAP差异 + SDK缺陷 + 执行总结
