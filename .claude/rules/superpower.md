---
title: skills
created: 2026-07-13
tags:
  - clippings
  - 教程
  - skills
---
superpowerskill 各个技能使用流程

搜索 3 个关键词，参考 15 篇资料

## Superpowers 全套 14 个 Skill 完整使用流程

Superpowers 是一套 AI 编程标准化工作流技能包，适配 Claude Code，分 **需求设计、环境隔离、任务规划、开发执行、调试排错、评审验证、分支收尾、高级并行** 八大类，每个 Skill 独立固定流程，可自动串联或手动 `/skill名` 触发。

![image](https://p11-flow-imagex-sign.byteimg.com/tos-cn-i-ezhpy3drpa/f51a2e3647d542b181a6b8d98c7bab95~tplv-a9rns2rl98-pc_smart_face_crop-v1:512:384.image?lk3s=8e244e95&rcl=20260713134212D940E8486DA65A25418E&rrcfp=cee388b0&x-expires=2099281340&x-signature=Tp8nZ%2FN00Ctci13R5rNzUl%2F1i40%3D)

Superpowers完整流水线

## 一、需求设计类（开发第一步，禁止直接写代码）

### 1\. brainstorming 头脑风暴（需求澄清 + 方案设计）

**触发时机** ：新功能、重构、大型需求启动 **完整流程**

1. AI 主动追问缺失需求：边界、输入输出、性能、兼容、UI、异常场景
2. 整理全部疑问，一次性向用户确认
3. 输出多套技术方案对比（优缺点、成本、风险）
4. 生成正式设计文档 `design.md` （架构、文件修改清单、验收标准）
5. **等待用户明确批准** ，未批准不进入下一步
6. 用户驳回则重新迭代方案；用户同意进入 writing-plans

**调用方式** ： `/brainstorming`

### 2\. systematic-debugging 系统化排错（Bug 专用）

**触发时机** ：报错、测试失败、程序行为异常 **完整流程**

1. 收集全部线索：报错堆栈、复现步骤、输入数据、预期结果
2. 分层缩小范围：环境→依赖→接口→业务逻辑→数据
3. 提出多条可验证根因假设，逐条设计复现测试
4. 执行验证，定位真实根因
5. 给出修复方案 + 配套测试用例
6. 运行验证，确认 Bug 彻底解决
7. 记录故障复盘文档

**调用方式** ： `/systematic-debugging`

## 二、环境隔离类（代码操作前隔离工作区）

### 3\. using-git-worktrees Git 隔离工作区

**触发时机** ：计划执行前，避免污染主分支 **完整流程**

1. 检查项目`.gitignore` ，自动添加 worktree 目录忽略规则
2. 创建独立隔离工作树 + 专属开发分支
3. 自动进入隔离目录，安装项目依赖
4. 执行基线测试，确保初始代码无报错
5. 全程所有代码修改仅作用于隔离 worktree，不改动主目录
6. 任务结束后随 finishing-a-development-branch 统一清理

**调用方式** ： `/using-git-worktrees`

## 三、任务规划类（拆解可落地执行清单）

### 4\. writing-plans 编写实施计划

**触发时机** ：设计方案用户确认后 **完整流程**

1. 基于 `design.md` 拆解 **2–5 分钟单步小任务**
2. 每条任务明确：修改文件路径、代码范围、操作命令、验证方式
3. 输出 `tasks.md` 任务清单，带复选框
4. 标注任务依赖顺序、风险点、回滚方案
5. 交付用户确认计划，无异议才启动开发执行
6. 用户提出修改则重新调整任务清单

**调用方式** ： `/writing-plans`

## 四、开发执行核心类（TDD 开发闭环）

### 5\. test-driven-development TDD 测试驱动开发（单任务最小单元）

**触发时机** ：每个子任务实现阶段 **固定红 - 绿 - 重构三循环**

1. RED（红）：先写预期失败的单元 / 集成测试，运行确认报错
2. GREEN（绿）：编写最少业务代码，让测试全部通过
3. REFACTOR（重构）：优化代码可读性、性能、规范，全程保持测试通过
4. 输出测试覆盖率、执行日志作为凭证

**调用方式** ： `/test-driven-development` / `/tdd`

### 6\. executing-plans 顺序执行计划（轻量单代理开发）

**触发时机** ：简单小型任务，无并行需求 **完整流程**

1. 读取 `tasks.md` 按顺序逐条执行
2. 每条任务强制走 TDD 红 - 绿 - 重构
3. 单任务完成后自动执行 requesting-code-review 自检
4. 所有任务完成后执行 verification-before-completion 全量验证
5. 全部校验通过进入分支收尾流程

### 7\. subagent-driven-development 子代理驱动开发（复杂多模块）

**触发时机** ：前后端分离、多文件重构、大型功能 **完整流程**

1. 拆分任务为独立模块，派发多个子 Agent 并行处理
2. 每个子 Agent 独立执行 TDD 开发、自测
3. 主 Agent 统一汇总所有子模块代码，处理模块依赖冲突
4. 整体全量测试 + 统一代码审查
5. 合并所有变更，生成完整交付代码

## 五、代码评审类（质量关卡，阻塞不合格代码）

### 8\. requesting-code-review 发起代码自检评审

**触发时机** ：单任务完成、全部开发结束 **完整流程**

1. 多维度审查：需求匹配、代码规范、安全漏洞、测试覆盖、性能、边界异常
2. 问题分级：严重（阻塞）/ 建议 / 优化提示
3. 严重问题必须修复，不允许进入下一阶段
4. 输出评审报告，列出待修改点
5. 交付用户确认评审结果

### 9\. receiving-code-review 接收外部评审反馈

**触发时机** ：用户给出 Review 修改意见 **完整流程**

1. 逐条解析评审意见，区分合理修改 / 需求争议
2. 对争议点主动和用户确认需求标准
3. 按意见修复代码，同步更新对应测试用例
4. 重跑全部测试，验证修改无副作用
5. 重新发起 requesting-code-review 二次自检

## 六、交付验证类（杜绝 “假完成”）

### 10\. verification-before-completion 交付前全量验证

**触发时机** ：所有代码 + 评审完成，收尾前强制校验 **完整流程**

1. 完整执行项目全量测试（单元 + 集成 + 功能）
2. 校验需求全部完成，无遗漏任务
3. 输出验证证据：测试日志、覆盖率、运行截图、接口返回数据
4. 检查代码无硬编码、无注释残留、无调试打印
5. 全部验证通过才允许进入分支收尾

## 七、分支收尾类（代码集成、环境清理）

### 11\. finishing-a-development-branch 完成开发分支

**触发时机** ：验证全部通过，任务结束 **完整流程**

1. 再次运行全量测试，确认基线稳定
2. 展示 4 种操作选项供用户选择：
	- 本地合并到主分支
	- 推送远程创建 Pull Request
	- 保留当前隔离分支，后续继续迭代
	- 丢弃全部变更（需输入 `discard` 二次确认）
3. 执行用户选择的操作
4. 自动清理 git worktree 隔离目录，释放环境

## 八、高级扩展技能（并行、自定义）

### 12\. dispatching-parallel-agents 并行多代理任务分发

**触发时机** ：无依赖的多独立任务（前端页面、数据库脚本、接口文档） **流程**

1. 识别可并行执行的独立任务
2. 分配多个 Agent 同时开发，互不阻塞
3. 统一收集所有输出，处理交叉依赖冲突
4. 合并代码后统一测试评审

### 13\. skill-creator 自定义 Superpowers 技能

**触发时机** ：现有流程不匹配团队规范，需要固化专属流程 **流程**

1. 收集你的固定工作步骤、校验规则、输出模板
2. 生成标准化 Markdown Skill 文档，定义触发条件、执行步骤、输出物
3. 本地导入 Superpowers 套件，可直接调用自定义 skill
4. 支持复用、修改、导出分享

### 14\. parallel-verification 并行多维度验证

**触发时机** ：上线前高强度校验 **流程**

1. 多 Agent 同时并行执行：单元测试、静态代码扫描、安全审计、性能压测
2. 汇总所有校验报告，标记所有风险项
3. 风险项全部修复后才可交付

## 完整标准开发流水线（技能串联顺序）

1. brainstorming（需求设计 + 用户确认）
2. using-git-worktrees（创建隔离区）
3. writing-plans（拆解任务 + 用户确认计划）
4. subagent-driven-development /executing-plans（执行开发，内部循环 TDD）
	- 单任务内：test-driven-development → requesting-code-review
5. receiving-code-review（处理用户反馈迭代）
6. verification-before-completion（全量验证）
7. finishing-a-development-branch（分支集成收尾）

## 三种调用技能的方式

1. **自动触发** ：安装 Superpowers 后，AI 自动判断场景调用对应 Skill（写新功能自动走 brainstorming，报错自动走 systematic-debugging）
2. **斜杠命令手动指定** ：对话输入 `/writing-plans` 、 `/tdd` 强制启动对应流程
3. **自然语言触发** ：直接描述 “使用 superpowers 的 systematic-debugging 排查这个报错”

