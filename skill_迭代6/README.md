# claude code测试设计生成

### step1：使用"skill_其他"目录下面的skill生成依赖文件，同一项目可以复用，不用重复生成
```commandline
claude执行目录下需要创建ai_reference目录, 依赖文件
        1、框架端到端场景: e2e_framework_scenes.md（必选）
            --使用skill_其他/extract-framework-e2e这个skill生成，示例：/extract-framework-e2e /path（开发仓根目录）
        2、测试框架aw复用模板：framework_reference.md（需要生成自动化代码必选，只生成测试设计不需要）
            --使用skill_其他/extract-framework-aw这个skill生成，示例：/extract-framework-aw /path（测试仓根目录）
        3、测试框架自动化用例模板：test_common_template.md（需要生成自动化代码必选，只生成测试设计不需要）
            --使用skill_其他/extract-test-template这个skill生成，示例：/extract-test-template /path (测试仓示例代码目录，用于提取格式，建议不要包含太多文件的目录)
        4、待测试需求示例代码：test_req_template.md（非必选，可以直接放写好的smoke用例，提高ai生成质量）
            --直接拷贝写好的示例代码放这个md文件
tips：开源场景可以直接用"ai_reference_开源直接用"目录下的内容，其他业务场景需要使用skill生成
```


### step2：使用"skill_迭代*"目录下面的skill：req-test-analyzer 生成测试设计和测试代码

```commandline
示例使用1：传代码代码目录、需求文件和框架端到端场景：
/req-test-analyzer ai_reference/README.md（需求文档路径） openjiuwen/core/session/interaction（代码路径） --framework-scenes ai_reference/e2e_framework_scenes.md（框架端到端场景，参考step1）
```

```commandline
示例使用2：不传代码，只传需求文件和框架端到端场景：
/req-test-analyzer ai_reference/README.md（需求文档路径）  --framework-scenes ai_reference/e2e_framework_scenes.md（框架端到端场景，参考skill_迭代2/README.md）
```

```commandline
示例使用3：不传代码目录场景，支持传单个/多个pr、或者单个/多个commit
/req-test-analyzer ai_reference/README.md（需求文档路径） --pr 123,124,125（PR号，多个用逗号隔开）--repo-url https://gitcode.com/openJiuwen/agent-core（git地址） --base develop（代码分支） --framework-scenes ai_reference/e2e_framework_scenes.md（框架端到端场景，参考step1） 
```



### 使用tips：
```
1、需求文档是测试设计主要来源，生成好的测试设计需要文档包含
    完整的端到端用户操作链路（不同功能）、对外接口定义、约束和参数说明
2、有测试框架的可以直接在测试框架目录下打开claude窗口，并准备好执行环境阶段，4生成测试用例会生成后尝试修复三次生成最后能通过的用例
3、文档中有示例代码，或者用户提供示例代码（test_req_template.md），能有效提高用例质量
4、有测试框架代码，并用skill_其他/extract-framework-aw 提取出了框架信息，能提高用例质量
5、测试设计生成完之后，可以人工评审下测试设计，简化后给出最终的test_design.json ，从阶段4重新开始执行，原有命令加上参数--start-stage 4
    如果不关注需求和其他框架场景的叠加，或者阶段3a代码分析出来的GAP场景，可以直接让模型合并test_design_batch_*.json中的部分场景重新生成test_design.json 
6、阶段4a会先生成level0用例，会有个人工检视点，一定要和模型多轮沟通保证level0用例正确，会直接影响阶段4b其他用例批量生成的质量
7、生成目录：
    {output_dir}/
    ├── requirement_analysis.md       # 阶段1（需求分析摘要）
    ├── code_analysis.md              # 阶段2（代码分析摘要）
    ├── test_design.json              # 阶段3b（Python merge生成，总的测试设计）
    ├── test_design_batch_*.json      # 阶段3a（测试设计的部分*）
    ├── test_{case_id}.py             # 阶段4
    ├── report.md                     # 阶段5 （最终的报告）
    └── .state/
        ├── skeleton/                  # 阶段1（文档中的示例代码、或者是用户提供的示例代码：test_req_template.md）
        ├── progress.json
        ├── s1_scenarios/              # 阶段1（文档提取的主要测试场景，以及测试场景的展开，是test_design.json的来源1）
        │   ├── FS-001.json
        │   └── ...
        ├── s3a_enriched/              # 阶段3a（S1场景复制 + GAP场景--test_design.json的来源2）
        │   ├── FS-001.json
        │   ├── FS-GAP-001.json
        │   └── ...
        ├── s3a_framework.json         # 阶段3a-fw（框架场景--test_design.json的来源3）
        └── results/                   # 阶段4
            └── {case_id}.json

```
