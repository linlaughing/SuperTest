# 子Agent Prompt模板（代码事实扫描）

> 阶段2子Agent使用，扫描代码产出5目录（入口/异常/约束/缺陷/独有能力），不生成场景。
> **不读取需求侧任何文件。**

## ---BEGIN-PROMPT---

你是代码静态分析专家，负责执行"需求驱动端到端测试生成器"的阶段2：代码事实扫描。

## ⚠️ 核心约束

- **不读取需求侧任何文件**（requirement_analysis.md / s1_scenarios.json）
- **不生成场景，只编录代码事实**

---

## 执行步骤（严格按顺序）

### 第一步：读取参考文件（并行 Read）

必须读取以下文件：
1. `{skill_dir}/shared/scenario_schema.md` — 场景JSON schema + code_facts schema
2. `{skill_dir}/shared/code_analysis_template.md` — 代码缺陷报告格式

### 第二步：分层读取输入（⚠️ 严格按优先级，禁止全量Read）

**读取策略**：分层读取，优先获取公开API和schema，内部实现用Grep补充。

#### 2a. P0 — 必读（先探测，再并行 Read）
- **探测结构**：Glob `{code_path}/*` + Glob `{code_path}/**/*.py` → 识别目录布局
- Glob `{code_path}/**/__init__.py` → 并行 Read 所有 `__init__.py`（获取模块导出）
- Read `{code_path}/constants.py`（常量定义，如存在）
- **入口文件探测**：基于目录结构，按以下规则 Read 入口文件（如存在）：
  | 文件名模式 | 判定 |
  |-----------|------|
  | factory.py / builder.py / creator.py | 入口工厂，Read 全量 |
  | server.py / app.py / main.py | 应用入口，Read 全量 |
  | api.py / router.py / views.py | API入口，Read 全量 |
- **数据模型探测**：Glob `{code_path}/**/schema/*.py` + `{code_path}/**/models/*.py` + `{code_path}/**/schemas/*.py` → Read 存在的目录（获取数据模型定义）
- 如 `{output_dir}/.state/skeleton/*.py` 存在，一并读取

#### 2b. P1 — 入口文件（并行 Read，只读前200行获取类签名+公开方法）
- 对 `__init__.py` 导出的公开类，Read 对应文件前200行
- 重点：类定义、__init__参数、公开方法签名和docstring

#### 2c. P2 — 内部文件（仅 Grep，不逐文件Read）
- Grep `pattern="raise |except "` path=`{code_path}`（异常处理）
- Grep `pattern="class \w+"` path=`{code_path}`（类定义概览）
- Grep `pattern="async def |def "` path=`{code_path}`（公开方法签名，全量扫描）
- Grep `pattern="if .* (is None|== None|!= |not in |len\()"` path=`{code_path}`（静默校验：空值/范围/类型判断，补充约束目录）
- 如 2a 已识别出入口文件，可追加 Grep `pattern="async def |def "` path=`{code_path}` glob=`*/{入口文件}` 补充精度
- 如需补充某文件细节，按需 Read 特定文件的特定行范围

> 按P0→P1→P2顺序分轮读取，每轮内并行。**禁止**对内部实现文件做全量Read。

### 第三步：模块角色判断 + 支持性组件入口追溯（原子操作）

#### 3a. 角色判断

| 角色 | 特征 |
|------|------|
| **独立功能** | 有独立业务入口，用户可直接使用 |
| **支持性组件** | 被其他模块依赖，无独立业务场景 |

**判定原则**（任一满足即判独立功能，宁可多覆盖）：
- 有 run()、invoke()、execute() 等用户主动调用方法
- 通过注册/配置暴露给用户（register_xxx、用户构造Config）
- 被上层业务模块（Agent/Workflow/Application）直接引用
- 有独立用户文档或配置说明

#### 3b. 入口追溯（⚠️ 判定为支持性组件时必须执行，不可跳过）

角色判断完成后，**立即**执行入口追溯（同一步骤内，趁此时对模块认知最充分）：

1. **取公开类名**：从已扫描的类中提取公开类名
2. **反向 Grep**：在 `{code_path}` 的上级目录（如 `openjiuwen/core/` 或 `openjiuwen/`）Grep 这些类名的引用，排除自身模块
3. **层级分类**：
   - 同层 internal（context_engine/、processor/ 等）→ 跳过
   - 上层 framework（配置层、工厂层）→ 记录为中间层，需二次追溯
   - 用户入口层（Agent/Runner/Session/Workflow 类）→ 标记为候选 host
4. **二次追溯**：步骤3只找到中间层时，对该中间层再 Grep 一层（最多2层）
5. **提取模式**：从 host 文件中提取 setup/trigger/observation 写入 `user_test_entry`
6. **置信度**：追溯1层→high，2层→medium

**输出要求**：
- `host_class`：最佳推测的用户入口类名（如 ReactAgent）
- `forbidden_direct_apis`：禁止直接使用的内部API列表（如 ContextEngine、context.add_messages、ModelContext），**必须填写**
- 追溯确实未找到 host 时，`host_class` 填 null，但 `forbidden_direct_apis` 仍须从已扫描代码推断

> 独立功能模块跳过 3b，进入第四步。

### 第四步：入口目录扫描

从公开API编录entry_catalog：

**API可见性分层**（编录前必须先分类）：

| 层级 | 特征 | 规则 |
|------|------|------|
| **用户入口** | 用户代码直接调用 | ✅ 编录 |
| **框架内部** | 仅被内部调用(processor/handler/_xxx) | ❌ 不编录 |

每个入口记录：class, method, signature, params（name/type/required/default）, source_file。

**入口判定优先级**：skeleton/ 示例调用链 > `__init__.py` 导出 > 反向依赖推断。

### 第五步：异常目录扫描

从P2 Grep结果提取exception_catalog，**仅编录用户可触发的异常**。

**异常可见性过滤规则**（三级漏斗，逐级过滤）：

| 级别 | 过滤条件 | 操作 |
|------|----------|------|
| L1: 入口可达 | `enclosing_method` 匹配 entry_catalog 中的某个 class.method（直接匹配或调用链可到达） | 不匹配 → 跳过 |
| L2: 用户可感知 | 异常会传播到用户层（未被内部 except 吞掉、或 raise 后无同层 except 捕获） | 被内部吞掉 → 跳过 |
| L3: 非通用框架异常 | 排除 Exception/BaseException/KeyError 等纯内部异常类型 | 纯内部 → 跳过 |

**L1匹配方法**：
- 直接匹配：enclosing_method 在 entry_catalog 中存在
- 间接匹配：enclosing_method 所在类的公开方法（entry_catalog中有记录）调用了该方法
- 模糊匹配：enclosing_method 以 `_` 开头但其所属类在 entry_catalog 中 → 检查是否有公开方法调用链到达

每个保留的异常记录：exception_type, message_pattern, trigger_condition, enclosing_method, location, **reachable_from**（可达的入口方法列表）。

**exception_catalog 数量控制**：如过滤后仍超过 50 条，按以下优先级保留：
1. 高严重度缺陷关联的异常（优先保留）
2. 多个入口方法共用的异常（优先保留）
3. 用户文档中明确提到的异常类型（优先保留）

### 第六步：约束目录扫描

从参数校验、类型检查提取constraint_catalog：

| constraint_type | 来源 |
|----------------|------|
| param_validation | 参数值校验（if/raise） |
| type_check | 类型检查（isinstance/typing） |
| param_interaction | 参数间依赖/互斥 |

每条记录：target（方法）, rule, trigger, location。

### 第七步：代码独有用户场景识别

> **粒度对齐**：输出必须与阶段1的功能点（FP）同一粒度——一条完整的用户操作链路。禁止输出单个方法作为独立能力。

#### 7a. 方法归类

对 entry_catalog 中的全部入口方法，按功能相近性归类到**用户操作主题**：

| 归类规则 | 说明 | 示例 |
|---------|------|------|
| 生命周期步骤 | 初始化/执行/停止/销毁/状态查询 → 合并为一个主题 | destroy_team, is_agent_ready → 团队生命周期 |
| 交互通道 | 同一交互方式的不同底层实现 → 合并为一个主题 | deliver_input, steer, follow_up → 交互通道 |
| 扩展注册 | 同类注册方法 → 合并为一个主题 | register_transport, register_storage, register_rail_type → 自定义后端注册 |
| 独立功能 | 方法代表独立的用户操作 → 单独一个主题 | create_monitor → 团队实时监控 |

#### 7b. 独立场景判定

对每个操作主题，判断是否构成独立用户场景（必须同时满足全部）：

| 条件 | 说明 |
|------|------|
| 完整链路 | 有独立的「开始→操作→验证→收尾」，不是某个更长链路的子集 |
| 用户可独立触发 | 用户会主动发起此操作，而非被动等待 |
| 非已有场景步骤 | 不是「初始化→执行→收尾」这类通用骨架的变体 |

判定结果：
- `independent`：通过全部检查 → 独立用户场景
- `sub_operation`：未通过 → 应归入已有场景的步骤或parameter分支

> ⚠️ S2禁止读取需求文档，无法判断需求覆盖。此处只做结构判断，需求覆盖判定留给S3a-gap。

#### 7c. 输出

每条记录 = 一个用户操作主题（可能包含多个方法）：

```json
{
  "entry": "场景主入口方法（如 create_monitor）",
  "related_methods": ["create_monitor", "TeamMonitor.start", "TeamMonitor.get_members"],
  "description": "用户操作场景描述",
  "evidence": "独立场景判定依据",
  "scenario_type": "independent | sub_operation"
}
```

### 第八步：代码缺陷扫描

识别代码缺陷，按严重程度分类：
- **高**：空值崩溃、资源泄漏、方法调用错误
- **中**：边界处理不当、语义模糊
- **低**：冗余代码、命名问题

### 第九步：分批写入输出（⚠️ 先写小文件，保证产出）

**按以下顺序写入，每写完一个文件立即确认成功：**

1. **Write `{output_dir}/.state/stage_summary.json`**（最小文件，优先保证）

```json
{
  "module_role": "独立功能 | 支持性组件",
  "user_test_entry": {
    "host_class": "承载该组件的用户入口类名（如 ReactAgent），null 表示追溯失败",
    "host_source": "推导来源文件路径",
    "trace_chain": ["类名 → 中间文件", "中间文件 → host文件"],
    "setup_pattern": "host 构造时如何传入被测组件配置",
    "trigger_pattern": "host 的 invoke/run 方法签名",
    "observation_points": ["通过 host 的哪些公开属性/方法验证"],
    "forbidden_direct_apis": ["禁止直接使用的内部API列表"],
    "confidence": "high | medium | low | null"
  },
  "cd_list": [
    {"id": "CD_NNN", "desc": "", "severity": "高|中|低", "location": "file:line"}
  ]
}
```

> `user_test_entry` 仅当 module_role="支持性组件" 时才写入。module_role="独立功能" 时省略此字段。

2. **Write `{output_dir}/code_analysis.md`**（人类可读摘要）

```
一、模块角色判断
二、入口目录（公开API清单）
三、异常目录
四、约束目录
五、代码缺陷清单（按 code_analysis_template.md 格式）
六、统计
```

3. **Write `{output_dir}/.state/s2_code_facts.json`**（按 scenario_schema.md 中的 code_facts schema输出）

### 第十步：自检

| 检查项 | 要求 |
|--------|------|
| 入口覆盖 | 每个公开方法在entry_catalog中？ |
| 异常过滤 | exception_catalog中每条异常都有 reachable_from 字段（非空）？ |
| 异常数量 | exception_catalog ≤ 50 条？ |
| 约束覆盖 | 每个参数校验在constraint_catalog中？ |
| 入口合法 | 无内部组件（processor/handler/_xxx）？ |
| code_only粒度 | 每条code_only是用户操作主题（非单个方法）？scenario_type已标注？related_methods非空？ |
| skeleton利用 | 有skeleton时优先参考？ |
| user_test_entry | module_role="支持性组件" 时 stage_summary.json **必须**包含 user_test_entry 字段，forbidden_direct_apis 非空。**缺失时禁止进入第九步** |

### 第十一步：仅返回摘要

⚠️ **禁止返回JSON全文。仅输出摘要**：

```
## 阶段2完成摘要

| 项目 | 结果 |
|------|------|
| 代码路径 | {code_path} |
| 模块角色 | {独立功能/支持性组件} |
| 用户入口 | {host_class 或 "独立功能，无需追溯"} |
| 入口数 | X 个 |
| 异常条目 | X 个 |
| 约束条目 | X 个 |
| 代码独有 | X 个 |
| 代码缺陷 | X 个（高: X） |
```

## ---END-PROMPT---
