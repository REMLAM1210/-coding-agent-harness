# AGENT_LOG.md — 智能体协作日志

> 按时间顺序记录关键节点。每条包含：阶段、触发的 Superpowers 技能、subagent 输出关键片段/commit hash、人工干预、教训。

---

## 阶段 0: 规约与计划

### 0.1 Brainstorming
- **时间：** Session 1
- **技能：** `brainstorming`
- **关键 prompt：** "我要构建一个 Coding Agent Harness，聚焦反馈闭环维度"
- **智能体追问：** 聚焦维度？语言？LLM 供应商？架构形态？
- **我的决策：** 反馈闭环 / Python / NJU endpoint / Web-first
- **产出：** 设计 §1-§10 十节，逐节确认通过
- **教训：** 智能体的追问能暴露你没想到的约束（如 §4.11 要求线上部署）

### 0.2 SPEC.md 撰写
- **时间：** Session 1
- **技能：** `brainstorming` → 文档输出
- **产出：** SPEC.md v1（609 行）
- **自审：** 通过（无占位符、无矛盾、无歧义）
- **教训：** 自审标准太宽松——人工评审发现了 14 项问题

### 0.3 用户评审 → 14 项修改
- **时间：** Session 1
- **人工干预：** 我对 SPEC 提出了 4 项 🔴 必须修复 + 10 项 🟡 建议改进
- **关键修改：**
  - 🔴 ToolDispatcher 单点约定补充"内部顺序 guardrail.check → sandbox.execute"
  - 🔴 RawExecutionResult 作为显式数据契约
  - 🔴 SessionRegistry 归属 webui 层
  - 🔴 HITL TIMEOUT 复用 DENY 逻辑
  - 🟡 跨轮次失败集合比较算法
  - 🟡 失败类别优先级排序
  - 🟡 Sandbox 环境白名单（非黑名单）
- **产出：** SPEC.md v2（827 行），用户确认通过
- **教训：** 人工评审是不可或缺的——智能体自审无法发现自己的盲区

### 0.4 PLAN.md 撰写
- **时间：** Session 1
- **技能：** `writing-plans`
- **产出：** PLAN.md（20 个 TDD task，每个含完整测试代码 + 实现代码）
- **自审：** 通过（spec 覆盖完整、无占位符、类型一致）
- **教训：** PLAN 的参考代码存在内部矛盾（Task 3 测试与实现矛盾、Task 8 死代码），自审未发现

---

## 阶段 1: 实现（Subagent-Driven Development）

### Task 1: Core Data Models
- **技能：** `subagent-driven-development` + `test-driven-development`
- **subagent 输出：** 11/11 tests pass, commit `50a4879`
- **人工干预：** 无
- **reviewer 评审：** ✅ Approved，无 Critical/Important
- **教训：** 数据模型 task 是最简单的——纯数据类，无逻辑

### Task 2: LLMClient ABC + MockLLMClient
- **subagent 输出：** 14/14 tests, commit `3db22e3`
- **人工干预：** 无（subagent 自行修复了 MockExhausted 错误消息以匹配测试）
- **reviewer 评审：** ✅ Approved
- **教训：** subagent 能正确识别 PLAN 中的测试/实现矛盾并按 TDD 原则修复

### Task 3: Tool ABC + ToolDispatcher
- **subagent 输出：** 17/17 tests, commit `f1e008b` → `736c3b5` → `8a7e442`
- **人工干预：** 
  - 发现 ALLOW 分支绕过 sandbox 直接调用 tool → 派 fix subagent 恢复 `sandbox.execute` 路由
  - reviewer 发现 REQUIRE_APPROVAL 分支零测试覆盖 → 派 fix subagent 补 3 个测试
  - reviewer 发现 `self._tools` 死代码 → 移除 `tools` 参数
  - 更新 PLAN.md 中 5 处下游 task 的 ToolDispatcher 构造调用
- **reviewer 评审：** ❌ → fix → ❌ → fix → ✅ Approved（3 轮修复）
- **commit：** `dae4d2e`（PLAN.md 更新）
- **教训：** 这是最复杂的 task——架构约定、测试覆盖、死代码三个问题叠加。PLAN 参考代码的矛盾在这里暴露得最明显。

### Task 4: File Tools
- **subagent 输出：** 24/24 tests, commit `eb3990d` → `d3af782` → `7242eb8`
- **人工干预：**
  - reviewer 发现 ListFilesTool 无路径遍历防护 → 派 fix subagent
  - reviewer 发现 `_resolve_safe` 的 `startswith` 可被前缀混淆攻击 → 改用 `os.path.commonpath`
  - reviewer 发现 `commonpath` 在跨盘路径上抛 `ValueError` → 加 `try/except`
- **reviewer 评审：** ❌ → fix → ❌ → fix → ✅ Approved（2 轮修复）
- **教训：** 安全相关代码需要额外审查——PLAN 参考代码的安全实现不够严谨

### Task 5: Shell Tool + Feedback Tools
- **subagent 输出：** 30/30 tests, commit `05c7b25`
- **人工干预：** 无（subagent 自行处理了 Windows 上的 POSIX shell 选择和 timeout 消息矛盾）
- **reviewer 评审：** ✅ Approved（orphaned child on timeout 标记为 hardening item）
- **教训：** subagent 能合理处理跨平台问题和 PLAN 内部矛盾

### Task 6: Guardrail
- **subagent 输出：** 36/36 tests, commit `948346f`
- **人工干预：** 无
- **reviewer 评审：** ✅ Approved，无 Critical/Important
- **教训：** 纯函数 + 正则匹配是最容易正确实现的

### Task 7: Sandbox
- **subagent 输出：** 40/40 tests, commit `6d3789a`
- **人工干预：** 无
- **reviewer 评审：** ✅ Approved
- **教训：** sandbox 通过 `hasattr` 注入策略是脆弱耦合，但匹配 PLAN

### Task 8: HITL State Machine
- **subagent 输出：** 44/44 tests, commit `61676a1`
- **人工干预：** reviewer 发现 `else`/TIMEOUT 分支是死代码 → 我直接删除（7 行）
- **commit：** `db2b0b3`（删除死代码）
- **reviewer 评审：** ✅ Approved + 死代码已移除
- **教训：** PLAN 参考代码与 SPEC 约定矛盾时，以 SPEC 约定为准

### Task 9: Validators（反馈闭环 ①）
- **subagent 输出：** 51/51 tests, commit `0280e08`
- **人工干预：** 无
- **reviewer 评审：** ✅ Approved，无 Critical/Important
- **教训：** 用 forged input 测试解析器是最干净的方式——不需要真实 pytest/ruff/mypy

### Task 10: Classifier（反馈闭环 ②）
- **subagent 输出：** 57/57 tests, commit `8198df3`
- **人工干预：** 无
- **reviewer 评审：** ✅ Approved
- **教训：** 优先级合并逻辑用 `<` 严格比较实现 first-wins 是正确的

### Task 11: FeedbackLoop（反馈闭环 ③）
- **subagent 输出：** 62/62 tests, commit `708b612`
- **人工干预：** reviewer 发现 category-threshold 升级路径无测试 → 我直接添加测试（9 行）
- **commit：** `f3f9399`（补充测试）
- **reviewer 评审：** ✅ Approved + 测试已补充
- **教训：** 反馈闭环是项目核心贡献——停滞/振荡/收敛检测逻辑正确，但测试覆盖需要更严格

### Task 12: Memory Store + Config Loader
- **subagent 输出：** 69/69 tests, commit `24768be`
- **人工干预：** 无
- **reviewer 评审：** ✅ Approved
- **教训：** 基础设施 task 是机械性的——忠实转录即可

### Task 13: AgentRunner（主循环）
- **subagent 输出：** 73/73 tests, commit `f6bf296`
- **人工干预：** 无（4 个 Important robustness 问题标记为 hardening）
- **reviewer 评审：** ✅ Approved（异常处理、状态重置、离线测试、事件保真度标记为 hardening）
- **教训：** 主循环是最复杂的集成 task——PLAN 的参考代码基本正确，但缺少异常处理

### Task 14: RealLLMClient
- **subagent 输出：** 79/79 tests, commit `2ee82f7`
- **人工干预：** 无（subagent 自行处理了 OpenAI import 位置矛盾和 mojibake 字符）
- **reviewer 评审：** ✅ Approved（retry path 未测试标记为 follow-up）
- **教训：** RealLLMClient 的系统提示骨架是关键——后续运行测试发现 LLM 不提 Done 的问题

### Task 15: Credential Store
- **subagent 输出：** 85/85 tests → 96/96 tests, commit `0ffdf8a` → `aa5667b`
- **人工干预：**
  - reviewer 发现 None-backend 崩溃 → 派 fix subagent 加守卫
  - reviewer 发现缺少 .env 文件回退 → 派 fix subagent 实现 .env 解析
- **reviewer 评审：** ❌ → fix → ✅ Approved
- **教训：** 凭据安全是 §4.2 的核心——三层回退（keyring → env → .env）必须完整

### Task 16: WebUI Backend
- **subagent 输出：** 104/104 tests, commit `66ec74d`
- **人工干预：** reviewer 发现 `websockets` 未声明为依赖 → 我直接添加到 pyproject.toml
- **commit：** `b46a50f`（添加 websockets 依赖）
- **reviewer 评审：** ✅ Approved
- **教训：** FastAPI 的 TestClient 需要 websockets 包——依赖声明要完整

### Task 17: Frontend
- **subagent 输出：** commit `0e4fe8f`（3 个静态文件）
- **人工干预：** 无（跳过 review——纯静态文件）
- **教训：** 前端是 thin visualization layer，不需要深度 review

### Task 18: CLI Frontend
- **subagent 输出：** 106/106 tests, commit `7d0d606`
- **人工干预：** 无（跳过 review——thin CLI wrapper）
- **教训：** CLI 是 harness kernel 的薄封装

### Task 19: Mechanism Demos（A.6 硬性要求）
- **subagent 输出：** 109/109 tests, commit `637df60`
- **人工干预：** subagent 自行修改了 `agent_runner.py` 和 `base.py` 以发射 GuardrailDecision 事件
- **reviewer 评审：** ✅ Approved（subprocess spawning 标记为 hardening）
- **教训：** 三个机制演示是 A.6 硬性要求——guardrail 拦截、反馈自纠正、停滞检测全部通过

### Task 20: Dockerfile + CI + README
- **subagent 输出：** commit `3e70633`
- **人工干预：** 无
- **教训：** 分发是最后一环——Dockerfile + .gitlab-ci.yml + README 三件套

---

## 阶段 2: 最终评审与修复

### 2.1 Final Whole-Branch Review
- **技能：** `requesting-code-review`
- **reviewer 输出：** 2 Critical + 11 Important
  - C1: WebUI 不运行 agent（session 立即 finish）
  - C2: Dockerfile 构建顺序错误 + 无 .dockerignore + 无 [build-system]
  - I1: Validator 未按 source 路由（只有 PytestValidator）
  - I2: Memory 未接入主循环
  - I3: HITL 状态机孤立（ToolDispatcher 绕过它）
  - I4: 主循环无异常处理
  - I5: ToolCallResult 丢失 RawExecutionResult
  - I6: Guardrail 被检查两次
  - I7-I11: 测试隔离、并发计数、retry 测试、状态重置、sandbox 封装

### 2.2 修复
- **commit：** `15269ef` + `7e0e85a` + `8d972e3` + `1cf6300`
- **修复内容：**
  - C1: WebUI 在后台 task 中运行 AgentRunner，桥接 EventSink 到 WebSocket
  - C2: 修复 Dockerfile 构建顺序，添加 [build-system] 和 .dockerignore
  - I1: 按 action type 路由 validator（RunTests→Pytest, RunLint→Ruff, RunTypeCheck→Mypy）
  - I2: MemoryStore 接入 AgentRunner，关键词检索 + 运行后存储
  - I3: ToolDispatcher 内部创建 HitlStateMachine，发射 HitlApprovalRequired 事件
  - I4: 主循环 try/except，异常时发射 LoopFinished(reason="ERROR: ...")
  - I5: ToolCallResult 接受 ActionResult | RawExecutionResult
  - I6: 添加 dispatch_with_decision()，移除 runner 中的重复 guardrail 检查
- **测试：** 118/118 pass（109 原有 + 9 新增）
- **教训：** 最终评审暴露了"已实现但未接入"的模式——Memory、HITL、Ruff/Mypy validators 都是孤立组件

---

## 阶段 3: 运行验证

### 3.1 CLI 模式
- **commit：** `00b7f80`（改进 system prompt + 切换 model 到 glm-5.2）
- **问题：** 初次运行 LLM 一直重复 WriteFile，不提 Done → 改进 system prompt
- **结果：** ✅ agent 3 步完成（WriteFile → ReadFile → Done）

### 3.2 Web UI 模式
- **结果：** ✅ REST API + WebSocket 事件流 + 并发限制 + abort 全部正常

### 3.3 Docker 模式
- **结果：** ⛔ 本机未安装 Docker，未测试

---

## 统计

| 指标 | 数值 |
|---|---|
| 总 commit 数 | 35 |
| 总测试数 | 118 |
| subagent 派发次数 | 20 implementer + 20 reviewer + 6 fix = 46 |
| 人工直接修改 | 5 次（HITL 死代码、category-threshold 测试、websockets 依赖、system prompt、PLAN.md API 更新） |
| review 轮次 | 20 task review + 1 final review = 21 |
| Critical issue 修复 | 2（WebUI 不运行 agent + Dockerfile 错误） |
| Important issue 修复 | 6（validator 路由 + memory 接入 + HITL 接入 + 异常处理 + 事件保真 + guardrail 去重） |
