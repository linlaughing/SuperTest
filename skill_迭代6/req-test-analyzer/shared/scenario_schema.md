# 统一场景 JSON Schema

S1和S3a采用**拆分文件模式**：索引文件 + 逐场景文件。S2产出独立的 code_facts schema（见下方）。

## 文件组织

```
.state/
├── s1_index.json                    # S1轻量索引
├── s1_scenarios/                    # S1逐场景文件
│   ├── FS-001.json
│   ├── FS-002.json
│   └── ...
├── s3a_enriched_index.json          # S3a-code轻量索引
├── s3a_enriched/                    # S3a-code逐场景文件
│   ├── FS-001.json
│   └── ...
└── s3a_framework.json               # S3a-fw输出（单文件，通常较小）
```

## s1_index.json 结构（S1输出）

```json
{
  "meta": {
    "source": "requirement",
    "doc_path": ""
  },
  "function_points": [
    {
      "id": "FP-NNN",
      "name": "功能名称",
      "entry": "用户入口",
      "priority": "P0 | P1 | P2",
      "constraints": ["约束1"],
      "source_ids": ["FN_001"]
    }
  ],
  "scenario_index": [
    {
      "id": "FS-NNN",
      "name": "场景名称",
      "type": "flow",
      "priority": "P0 | P1 | P2",
      "fp_refs": ["FP-NNN"],
      "file": "s1_scenarios/FS-NNN.json"
    }
  ]
}
```

## 单场景文件结构（s1_scenarios/FS-NNN.json 和 s3a_enriched/FS-NNN.json 共用）

```json
{
  "id": "FS-NNN",
  "name": "场景名称",
  "type": "flow | framework | quality",
  "priority": "P0 | P1 | P2",
  "source": "requirement | code",
  "verify_points": ["验证点1"],
  "steps": [
    {
      "seq": 1,
      "action": "用户操作描述",
      "fp_ref": "FP-NNN",
      "data_scope": "数据实体/字段",
      "check": "成功判定"
    }
  ],
  "branches": {
    "parameter": [],
    "boundary": [],
    "exception": [],
    "quality": [],
    "constraint": [],
    "cross": []
  }
}
```

## s3a_enriched_index.json 结构（S3a-code输出）

在 s1_index 基础上增加富化元数据：

```json
{
  "meta": {
    "source": "requirement",
    "doc_path": "",
    "module_role": "独立功能 | 支持性组件"
  },
  "function_points": [
    {
      "id": "FP-NNN",
      "name": "功能名称",
      "entry": "用户入口",
      "priority": "P0 | P1 | P2",
      "constraints": ["约束1"],
      "source_ids": ["FN_001"],
      "code_entry": "真实代码入口（enriched时补充）",
      "gap_status": "matched | not_found | null"
    }
  ],
  "scenario_index": [
    {
      "id": "FS-NNN",
      "name": "场景名称",
      "type": "flow",
      "priority": "P0 | P1 | P2",
      "fp_refs": ["FP-NNN"],
      "file": "s3a_enriched/FS-NNN.json",
      "enriched_stats": {
        "+parameter": 0,
        "+boundary": 0,
        "+exception": 0,
        "+constraint": 0,
        "+quality": 0
      }
    }
  ],
  "fp_mapping": [
    {
      "fp_id": "FP-NNN",
      "status": "matched | not_found | code_only",
      "code_entry": ""
    }
  ],
  "gap_summary": {
    "not_implemented": ["FP-NNN"],
    "code_only": ["entry_name"]
  }
}
```

## e2e_scenes.json 结构（merge脚本输出，合并后单文件）

```json
{
  "meta": {
    "source": "requirement | code",
    "doc_path": "",
    "module_role": "独立功能 | 支持性组件"
  },
  "function_points": [ ... ],
  "flow_scenarios": [ ... ]
}
```

flow_scenarios 中每个元素与单场景文件结构相同，额外字段：
- framework_scene: 原始框架场景ID（仅 type=framework）
- linked_scene: 关联的flow场景ID（仅 type=framework/quality）
- skip_reason: 不可验证项标注（仅quality类型）

## 字段说明

### scenario_index（索引文件特有）

| 字段 | 必填 | 说明 |
|------|------|------|
| id | 是 | 场景编号 FS-NNN |
| name | 是 | 场景名称 |
| type | 是 | flow / framework / quality |
| priority | 是 | P0/P1/P2 |
| fp_refs | 是 | 涉及的FP ID列表 |
| file | 是 | 对应的场景文件相对路径 |

### function_points

| 字段 | 必填 | 说明 |
|------|------|------|
| id | 是 | 统一编号 FP-NNN |
| name | 是 | 用户可观测行为描述 |
| entry | 是 | 用户入口（类名.方法名 / 配置项） |
| priority | 是 | P0/P1/P2 |
| constraints | 是 | 约束条件列表，无则为空数组 |
| source_ids | 是 | 原始编号（["FN_001"] 或 ["CF_001"]） |
| code_entry | 否 | 真实代码入口（仅 s3a_enriched_index） |
| gap_status | 否 | matched/not_found（仅 s3a_enriched_index） |

### 单场景文件字段

| 字段 | 必填 | 说明 |
|------|------|------|
| id | 是 | 编号 FS-NNN |
| type | 是 | flow=流程 / framework=框架 / quality=质量 |
| verify_points | 是 | 主流程验证点列表 |
| steps | 是 | 至少1个步骤 |
| branches | 是 | 6类分支，无分支填空数组 |
| exploration_log | 否 | 追问发现记录（仅S1输出） |
| truncated_cross | 否 | 被截断的cross分支（仅id+description，超出5个上限时记录） |
| framework_scene | 否 | 原始框架场景ID（仅 type=framework） |
| linked_scene | 否 | 关联的flow场景ID（仅 type=framework/quality） |
| skip_reason | 否 | 不可验证项标注（仅quality类型） |

### exploration_log

| 字段 | 说明 |
|------|------|
| 追问轮次 | 执行的追问轮次数 |
| 新发现数 | 追问发现的新场景总数 |
| 终止原因 | 连续2轮无新发现 / 达到最大5轮 |

### steps

| 字段 | 说明 |
|------|------|
| action | 用户操作语言，禁止内部组件名 |
| fp_ref | 引用的FP id |
| data_scope | 该步骤处理的数据实体 |
| check | 该步骤的成功判定 |

### branches

每类分支的通用字段：

| 字段 | 说明 |
|------|------|
| id | FS-NNN-{类型缩写}{序号} |
| step_ref | 偏离的步骤序号（quality无此字段） |
| trigger | 触发/注入条件（boundary合并分支用values时不填，exception合并分支用sub_conditions时不填） |
| expected | 预期结果（同上，合并分支不填） |

类型特有字段：

| 类型 | 缩写 | 额外字段 | 说明 |
|------|------|---------|------|
| parameter | A | param, values | 参数名和取值列表 |
| boundary | B | param(可选), values(可选) | 同参数多边界值合并时使用：values=[{trigger,expected}]，与 trigger/expected 互斥 |
| exception | E | sub_conditions(可选) | 同步骤同类失败合并时使用：sub_conditions=[{trigger,expected}]，与 trigger/expected 互斥 |
| quality | Q | risk_ref | 关联RK/CD/GAP的ID |
| constraint | C | constraint | 约束规则描述 |
| cross | X | cross_refs, fp_refs | 引用的分支ID列表和涉及的FP |

**boundary values 合并格式**（同 step_ref + 同参数时使用）：
```json
{
  "id": "FS-001-B01",
  "description": "summary_target边界值",
  "step_ref": 1,
  "param": "summary_target",
  "values": [
    {"trigger": "summary_target=10(最小值)", "expected": "摘要按最小值生效"},
    {"trigger": "summary_target=2000(最大值)", "expected": "摘要按最大值生效"}
  ]
}
```

**exception sub_conditions 合并格式**（同 step_ref + 同类失败时使用）：
```json
{
  "id": "FS-001-E01",
  "description": "db_config无效",
  "step_ref": 1,
  "sub_conditions": [
    {"trigger": "db_config为None", "expected": "抛出配置校验异常"},
    {"trigger": "db_config连接信息错误", "expected": "抛出连接异常"}
  ]
}
```

> 注：有 values/sub_conditions 时，顶层 trigger/expected 不再填写。无合并的分支仍使用原 trigger/expected 格式。

### fp_mapping（仅 s3a_enriched_index）

| 字段 | 说明 |
|------|------|
| fp_id | FP编号 |
| status | matched / not_found / code_only |
| code_entry | 匹配到的代码入口（not_found时为空） |

### enriched_stats（仅 s3a_enriched_index 的 scenario_index）

| 字段 | 说明 |
|------|------|
| +exception | 新增异常分支数（从exception_catalog补充） |
| +quality | 新增质量分支数（从code_defects补充） |

> 注：parameter/boundary/constraint由阶段1覆盖，阶段3a不再富化。

## 编号规则

| 对象 | 编号格式 |
|------|---------|
| 功能点 | FP-001, FP-002... |
| 场景 | FS-001, FS-002... |
| 参数分支 | FS-001-A01, A02... |
| 边界分支 | FS-001-B01, B02... |
| 异常分支 | FS-001-E01, E02... |
| 质量分支 | FS-001-Q01, Q02... |
| 约束分支 | FS-001-C01, C02... |
| 组合分支 | FS-001-X01, X02... |

---

## s2_code_facts.json 结构（阶段2输出）

```json
{
  "meta": { "source": "code", "module_role": "...", "code_path": "..." },
  "entry_catalog": [...],
  "exception_catalog": [...],
  "constraint_catalog": [...],
  "code_defects": [...],
  "code_only_capabilities": [...]
}
```

### entry_catalog

| 字段 | 说明 |
|------|------|
| class | 公开类名 |
| method | 方法名 |
| signature | 完整方法签名 |
| params | [{name, type, required, default}] |
| source_file | 源文件路径 |

### exception_catalog

| 字段 | 说明 |
|------|------|
| exception_type | 异常类型 |
| message_pattern | 错误信息模式 |
| trigger_condition | 触发条件 |
| enclosing_method | 所在方法（class.method） |
| location | 文件:行号 |
| reachable_from | 可达的入口方法列表（class.method），用户可通过这些入口触发该异常 |

### constraint_catalog

| 字段 | 说明 |
|------|------|
| constraint_type | param_validation / type_check / param_interaction |
| target | 目标方法（class.method） |
| rule | 约束规则 |
| trigger | 触发条件 |
| location | 文件:行号 |

### code_defects

| 字段 | 说明 |
|------|------|
| id | CD-NNN |
| desc | 缺陷描述 |
| severity | 高/中/低 |
| location | 文件:行号 |

### code_only_capabilities

| 字段 | 说明 |
|------|------|
| entry | 场景主入口方法 |
| related_methods | 同一操作主题下的全部相关方法 |
| description | 用户操作场景描述 |
| evidence | 独立场景判定依据 |
| scenario_type | independent=独立用户场景 / sub_operation=应归入已有场景 |
