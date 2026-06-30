---
name: extract-framework-aw
description: 可复用资产抽取器。扫描测试项目中的公共模块、fixtures、基类、mock 服务、工具函数等，编录可复用资产并输出结构化参考文档。触发词："/extract-utils", "抽取工具资产", "提取复用资产", "扫描公共模块", "编录工具函数"
---

# 可复用资产抽取

扫描项目中的公共模块、fixtures、基类、mock 服务等，编录可复用资产。

> **职责边界**：本工具输出 `framework_reference.md`，是测试生成的**唯一 API 参考**。
> 包含：导入语句、模型配置、Fixture 用法、工具创建、组件配置、调用模式、约束规则、注意事项。

---

## 参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `project_path` | 测试项目根目录（必填） | - |
| `--output-dir` | 输出目录 | `<project_path>/ai_reference/` |
| `--language` | 编程语言（不指定则自动检测） | auto |
| `--focus` | 聚焦模块路径（可选，只分析指定子目录） | 无 |

---

## 上下文控制策略

Tool call 的返回值会**永久留在对话历史**中，Write 到磁盘不会释放上下文。因此：

1. **Grep 代替 Read**：Grep 只返回匹配行（可能 10 行），Read 返回整个文件（可能 500 行）。永远先 Grep，只在信息不足时才 Read
2. **head_limit 控制返回量**：所有 Grep 调用必须设置 `head_limit`，防止匹配结果过多
3. **子代理隔离**：子代理有独立上下文窗口。大项目必须用子代理分发，主上下文只收最终摘要
4. **流式组装**：最终文档用 Bash `cat` 拼接 section 文件，不要 Read 回来再 Write

---

## 产出格式约束

最终文档行数**不得超过400行**。以下规则适用于所有 section 文件和最终文档。

### R1 示例代码→1行调用链

**禁止**多行示例代码块。所有示例压缩为1行调用链：
```
agent=AgentBasic(); cfg,client=agent.get_model_request_client_cfg_from_env(client_id="test")
```
格式：`var=Class(args); var.method(args)`，用分号分隔语句。

### R2 调用模式→调用链表格

调用模式节**必须用表格**，列：场景|核心调用链|完整示例参考。

核心调用链用`→`分隔步骤，每步含方法名和关键参数。完整示例参考指向测试用例目录路径。

### R3 Mock服务→约束表格

Mock服务核心信息用**单个表格**，列：项目|说明。启动命令和地址写在标题旁`> 启动: ... | 地址: ...`。
删除预设数据代码块，改为单行摘要。工作原理/匹配规则/新增步骤压缩为表格行。

### R4 环境变量→单行

多行环境变量代码块压缩为单行斜杠分隔：`**环境变量**: `MODEL_PROVIDER/MODEL/MODEL_API_BASE/MODEL_API_KEY``

### R5 导入路径内联，删除附录

每个模块标题旁加`> 导入: from xxx import Yyy`行。文档末尾**不写附录导入路径表**。

### R6 约束速查置顶

文档头部新增**约束速查**节，列出所有模块的关键约束（每个约束1行），格式：
```
- AgentBasic: 环境变量必须配置MODEL_PROVIDER/MODEL/MODEL_API_KEY
- MockLLM: query必须包含responses/下JSON文件名前缀才能匹配
```

### R7 分隔线精简

模块间只用1个空行分隔，不写`---`分隔线。删除多余空行。

---

## 执行步骤

### 第零步：建立文件索引（轻量扫描）

**只使用 Glob 和 Grep，不 Read 任何文件。**

1. 用 Glob 扫描项目结构，识别公共目录：
   ```
   common/**/*.py, utils/**/*.py, fixtures/**/*.py,
   conftest.py, constants.py, mock_service/**/*
   ```

2. 用 Grep 签名扫描，**必须带 head_limit**（建议 50）：
   - `class ` → 类名和继承关系
   - `def ` → 函数签名（含参数）
   - `@pytest.fixture` → fixture 定义

3. 将索引写入 `{output_dir}/_index.json`，记录每个文件的路径和**估算行数**（通过 `wc -l` 或 Read 时观察）：
   ```json
   {
     "common_modules": [{"path": "...", "est_lines": 200}],
     "fixtures": [{"path": "...", "est_lines": 80}],
     "mock_services": [{"path": "...", "est_lines": 150}],
     "total_est_lines": 1200
   }
   ```

**决策分支**（基于估算总行数，非文件数）：
- `total_est_lines <= 3000`（约 15 个中等文件）：走单代理主流程
- `total_est_lines > 3000`：走子代理分发流程（见下方"子代理分发模式"）

---

### 第一步：扫描公共模块

**对每个公共模块文件：**

1. **优先用 Grep 提取**（不 Read 全文）：
   - 类定义行 + 继承关系
   - 函数签名行（含类型注解）
   - docstring 首行（紧跟在 class/def 下面的三引号行）

2. **只在以下情况 Read 全文**：
   - Grep 结果中参数类型注解缺失，需要从函数体推断
   - 类的公共方法列表不明确（如通过 `__init__` 动态绑定）
   - 需要提取约束/注意事项时

3. **每处理完一个模块，立即写入** `{output_dir}/_sections/` 目录：
   - 每个模块写一个独立文件，如 `_sections/module_agent_basic.md`
   - 写完后该模块的信息就可以从上下文中"释放"

提取信息：

1. **模块概述**：文件路径、功能描述
2. **类定义**：类名、继承关系、公共方法列表（含参数、返回值类型、用途说明）
3. **独立函数**：函数名、参数、返回值类型、用途
4. **常量/配置**：重要的常量定义
5. **约束/注意事项**：必须先调用xxx、不能xxx等

**产出格式**（严格遵守产出格式约束）：

```markdown
### 1.N xxx.py - 功能描述
> 导入: `from xxx import Yyy`

| 方法 | 参数 | 返回值 | 用途 |
|------|------|--------|------|
| `method1()` | ... | ... | ... |

**环境变量**: `ENV1/ENV2/ENV3`

**约束**: 必须先调用xxx()

**示例**: `var=Class(); var.method(param="value")`
```

---

### 第二步：扫描 Fixtures / Setup-TearDown

**只用 Grep 搜索，不 Read 全文件。**

- Python (pytest)：Grep `@pytest.fixture`，然后只 Read fixture 函数签名行
- Python (unittest)：Grep `def setUp` / `def tearDown`
- JS/TS：Grep `beforeEach` / `afterEach` / `beforeAll` / `afterAll`
- Java：Grep `@BeforeEach` / `@AfterEach`
- Go：Grep `func TestMain` / `t.Cleanup`

提取：fixture 名称、scope、参数、返回值。

**产出格式**：

```markdown
## 2. Fixtures

### conftest.py核心Fixtures

| Fixture | Scope | 用途 |
|---------|-------|------|
| `fixture_name` | function | 用途说明 |

**示例**: `with test_resource_manager() as rm: logger=rm.logger`
```

处理完立即写入 `{output_dir}/_sections/fixtures.md`。

---

### 第三步：扫描 Mock 服务

Glob 扫描 `mock_service/`、`mock/`、`mocks/` 目录下的文件列表。

对每个 mock 服务目录：
1. Read 入口文件（如 `__init__.py`、`server.py`、`main.py`）— 只读入口，不读全部
2. Grep 端口/路由定义（`port`、`@app.route`、`@router` 等）
3. Grep 配置数据文件格式（如 JSON/YAML schema）

提取：启动方式、接口端点、配置方式、数据格式、约束规则。

**产出格式**（严格遵守产出格式约束）：

```markdown
## 5. Mock服务

### 5.1 MockLLM - 大模型Mock
> 启动: `python mock_service/mockllm/main.py` | 地址: `http://localhost:8088`

| 项目 | 说明 |
|------|------|
| 核心文件 | `main.py`(入口), `server.py`(FastAPI), `responses/*.json`(按用例匹配) |
| API接口 | `POST /v1/chat/completions` |
| 默认工具名 | `{从AW类提取，如_add_2025}` |
| 工具参数 | `{从工具定义提取，如{"a":number,"b":number}}` |
| 匹配规则 | query包含responses/下JSON文件名前缀即匹配 |
| 新增用例 | 1.在responses/下创建`{case_id}.json` 2.确保query含文件名 3.启动服务 |
| 支持特性 | 流式响应、多轮对话、自定义延迟、tool_calls |

**约束**: query必须包含JSON文件名(不含.json后缀)才能匹配

**响应模板**: `{"responses":[{"stats_code":200,"response":{"tool_calls":[{"type":"function","id":"call_xxx","function":{"name":"{默认工具名}","arguments":"{参数示例}"}}]}},{"stats_code":200,"response":{"content":"..."}}]}`

### 5.2 Mock HTTP - HTTP接口Mock
> 启动: `python mock_service/mock_http/xxx.py` | 地址: `http://localhost:8000`

| 端点 | 方法 | 用途 |
|------|------|------|
| `/path` | GET | 说明 |

**预设数据**: 城市1/城市2/城市3 | **认证**: `X-API-Key:xxx`, `Authorization:Bearer xxx`
```

**MockLLM信息提取**（额外步骤）：
1. Grep `common/aw/` 搜索Agent基类的默认工具定义（如`_add_2025`）
2. Read 工具定义文件提取input_params格式
3. 填充到表格的"默认工具名"和"工具参数"行

多个同类Mock服务（如多个MCP SSE服务器）合并为单个表格，列：服务|启动命令|地址|工具。

处理完立即写入 `{output_dir}/_sections/mock_services.md`。

---

### 第四步：扫描工具函数

基于第零步索引中的函数列表，按类型归类：

1. HTTP 客户端
2. 文件读取器
3. 数据构建器
4. 验证器/断言工具
5. 日志工具
6. 环境配置
7. 等待/重试工具
8. 数据生成器

**如果函数签名+docstring已经足够说明用途，不需要再 Read 文件。**

**产出格式**：

```markdown
## 3. 工具函数(common/utils_aw/)

### xxx.py - 类名
> 导入: `from common.utils_aw.xxx import Class`

| 方法 | 参数 | 返回值 | 用途 |
|------|------|--------|------|
| `method()` | ... | ... | ... |

**示例**: `var=Class(args); var.method(param)`
```

处理完立即写入 `{output_dir}/_sections/utils.md`。

---

### 第五步：提取调用模式

用 Grep 搜索测试文件中的导入和调用（限制 head_limit 控制返回量）：

```
Grep "from common" cases/ --include="*.py" -n | head -30
Grep "import.*utils" cases/ --include="*.py" -n | head -30
```

从结果中识别 5 类模式：初始化、配置、执行、验证、清理。

每个模式只提取**核心调用链**（方法名+关键参数），不提取完整代码。同时记录一个最具代表性的测试用例目录路径。

**产出格式**（严格遵守产出格式约束）：

```markdown
## 4. 调用模式

| 场景 | 核心调用链 | 完整示例参考 |
|------|-----------|-------------|
| LLMAgent | `AgentBasic()._create_model_config()` → `LLMAgentBaseTest.create_base_llm_agent(cfg,prompt).add_tools([tool])` → `Runner.run_agent_streaming(agent,inputs)` | `cases/agent/llm_agent/` |
| ReActAgent | `AgentBasic().get_model_request_client_cfg_from_env()` → `ReactAgentBaseTest.create_base_react_agent(id,desc)` → `Runner.run_agent(agent,inputs)` | `cases/agent/react_agent/` |
```

处理完立即写入 `{output_dir}/_sections/patterns.md`。

---

### 第六步：流式组装最终文档

**不要 Read section 文件回来再 Write。** 用 Bash 直接拼接：

1. 先 Write 一个文档头部到 `framework_reference.md`
2. 用 Bash 追加各 section
3. 逐个追加，每个 section 只增加 Bash 调用结果（极少上下文）

```bash
cat _sections/modules_part1.md _sections/modules_part2.md _sections/fixtures.md _sections/utils.md _sections/mock_services.md _sections/patterns.md >> {output_dir}/framework_reference.md
```

**文档头部格式**：

```markdown
# {项目名称} 测试框架复用资产文档

> 版本: v1.0 | 更新: {timestamp}

## 目录
1. 公共模块 | 2. Fixtures | 3. 工具函数 | 4. 调用模式 | 5. Mock服务

## 约束速查
- AgentBasic: 环境变量必须配置MODEL_PROVIDER/MODEL/MODEL_API_KEY
- MockLLM: query必须包含responses/下JSON文件名前缀才能匹配
- MemoryBasic: 必须先set_test_context()再create_memory_engine()
[从各模块提取的关键约束，每个1行]
```

**不写附录导入路径表**（已内联到各模块标题`> 导入:`行）。

**组装完成后，用 Bash `wc -l` 检查最终文档行数，如超过400行则回溯精简**。

### 第七步：清理中间产物

最终文档生成后，删除所有中间文件，只保留 `framework_reference.md`：

```bash
rm -rf {output_dir}/_sections
rm -f {output_dir}/_index.json
```

**最终目录结构**：
```
{output_dir}/
└── framework_reference.md
```

---

## 子代理分发模式（估算总行数 > 3000）

### 分发策略

按目录/类型分为**最多 4 组**，每组分给一个 subagent：

| 组 | 职责 | 产出文件 |
|----|------|----------|
| 组A | 公共模块（common/、utils/） | `_sections/modules_part1.md` |
| 组B | 公共模块续（若 est_lines > 1500 则拆分） | `_sections/modules_part2.md` |
| 组C | Fixtures + 工具函数 | `_sections/fixtures.md` + `_sections/utils.md` |
| 组D | Mock 服务 + 调用模式 | `_sections/mock_services.md` + `_sections/patterns.md` |

### 子代理 Prompt 模板

子代理有独立上下文窗口，但仍需控制产出大小。**产出文件不得超过 80 行**，只记录摘要级信息。

```
你是资产抽取子代理。

文件列表：{从 _index.json 中按组分配的文件路径}
输出文件：{output_dir}/_sections/{assigned_filename}

规则：
1. 用 Grep 提取类/函数签名，不要 Read 全文
2. Grep 必须带 head_limit（建议 30）
3. 只记录摘要：类名、公共方法签名（参数+返回值）、docstring 首行
4. 每个模块用 markdown 表格，不要贴大段代码
5. 用 Write 写入指定路径

产出格式规则（必须遵守）：
- 每个模块标题旁加 `> 导入: from xxx import Yyy`
- 示例代码压缩为1行调用链，禁止多行代码块。格式：`var=Class(); var.method(param)`
- 环境变量用单行斜杠分隔：`**环境变量**: `ENV1/ENV2/ENV3``
- 约束信息写在一行：`**约束**: xxx`
- Mock服务标题旁加 `> 启动: ... | 地址: ...`
- Mock核心信息用表格，不写段落说明
- 调用模式用表格，列：场景|核心调用链|完整示例参考
- 模块间只用1个空行，不写`---`
- 产出文件控制在80行以内
```

### 主流程

1. 主代理：执行第零步，生成 `_index.json`
2. 主代理：根据 `total_est_lines` 决定是否启用子代理
3. 如启用：并行分发 Agent 调用，每个 subagent 独立处理并写入各自的 section 文件
4. 所有子代理完成后：主代理执行第六步（Bash cat 拼接），组装最终文档
5. 如不启用：主代理顺序执行第一步~第六步

---

## 完成检查清单

- [ ] 第零步索引已生成（含 est_lines），写入 `_index.json`
- [ ] 所有 Grep 调用都带了 head_limit
- [ ] 公共模块：签名优先提取，避免不必要的全文 Read
- [ ] 每个模块标题旁有 `> 导入:` 行
- [ ] 无多行示例代码块（应为1行调用链）
- [ ] 无多行环境变量代码块（应为单行斜杠分隔）
- [ ] 调用模式为表格格式（场景|核心调用链|完整示例参考）
- [ ] Mock服务标题旁有 `> 启动: | 地址:` 行
- [ ] Mock核心信息为表格格式，无段落说明
- [ ] Fixtures / Setup-Teardown 已编录
- [ ] 工具函数已按类型分组编录
- [ ] 文档头部有"约束速查"节
- [ ] 无附录导入路径表
- [ ] 模块间无`---`分隔线
- [ ] 最终文档通过 Bash cat 拼接，而非 Read 回来再 Write
- [ ] 最终文档行数 <= 400（`wc -l` 检查）
- [ ] `framework_reference.md` 已写入磁盘
- [ ] 中间产物已清理：`_sections/` 和 `_index.json` 已删除

## 完成输出

```
可复用资产抽取完成
| 项目 | 结果 |
|------|------|
| 公共模块 | {count} 个 |
| Fixtures | {count} 个 |
| Mock 服务 | {count} 个 |
| 工具函数 | {count} 个 |
| 调用模式 | {count} 种 |
| 处理模式 | {单代理 / 子代理分发（N组）} |
| 文档行数 | {行数} / 400 上限 |
| 输出 | ai_reference/framework_reference.md |
```
