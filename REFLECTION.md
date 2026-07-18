# REFLECTION.md — 反思报告

> 本反思报告由学生本人撰写，AI 仅用于辅助润色。

---

## 一、Superpowers 技能的实际效果

### 发挥最大作用的技能

**`brainstorming`** 是整个流程中价值最高的技能。它不是简单地"问你想做什么"，而是通过分节呈现 + 逐节确认的模式，强制我在进入实现之前就把每个设计决策想清楚。最典型的例子是：我最初选了 Library-first 架构，智能体追问"通用要求 §4.11 要求线上部署 WebUI"，促使我改选 Web-first。如果没有这个追问，我会在实现到一半时才发现架构选错了。

**`subagent-driven-development`** 是第二有价值的技能。它的核心洞察是：每个 task 派一个全新 session 的 subagent，只给它 task brief + 必要接口信息，不继承任何对话历史。这天然满足了 §4.5 的冷启动验证要求——每个 subagent 都是一个"陌生智能体"，它会在你未明文写下的每个假设处受阻。事实上，Task 3 的 ToolDispatcher 路由矛盾、Task 4 的路径遍历防护缺陷、Task 15 的 None-backend 崩溃，都是在 subagent 实际编写测试时暴露的，而 SPEC 自审和 PLAN 自审都没有发现这些问题。

**`test-driven-development`** 的价值在于"先红再绿"的纪律。在 AI 协作场景下，LLM 生成代码时很容易"先写实现再补测试"——测试变成了对实现的描述而非验证。TDD 技能强制 subagent 先写失败测试、确认失败原因正确、再写实现，这保证了测试是在验证行为而非验证实现。

### 形式大于实质的技能

**`using-git-worktrees`** 在本项目中形式大于实质。通用要求鼓励用 worktree 隔离每个功能模块，但本项目是一个从零开始的新项目，没有需要隔离的现有工作。subagent-driven development 本身已经提供了隔离——每个 subagent 在独立的 session 中工作。worktree 的价值在大型现有代码库中更高。

**`finishing-a-development-branch`** 的选项菜单（merge/PR/keep/discard）在个人项目中略显形式化。个人项目没有"团队评审 PR"的环节，merge 和 keep 的区别不大。但它的"验证测试 → 再决定"的纪律是有价值的。

---

## 二、TDD 在 AI 协作下是阻碍还是放大器

TDD 是**放大器**，但有一个前提：PLAN 中的测试代码必须正确。

在本项目中，PLAN 为每个 task 提供了完整的测试代码和实现代码。subagent 的工作本质上是"转录 + 测试"。当 PLAN 的测试代码与实现代码矛盾时（如 Task 3 的 ToolDispatcher），TDD 的"测试是真理"原则反而帮助 subagent 做出了正确选择——以测试为准，修复实现。

但 TDD 也有一个盲区：如果 PLAN 的测试代码本身有缺陷（如 Task 4 的路径遍历测试只测了一个攻击向量），TDD 不会帮你发现测试覆盖不足。这需要 reviewer 来补充——事实上 reviewer 确实发现了 `ListFilesTool` 无防护和 `startswith` 前缀混淆问题。

结论：TDD 在 AI 协作下是放大器，但需要配合严格的 code review 才能覆盖 TDD 自身的盲区。

---

## 三、Subagent 自主运行时长与 task 颗粒度

在本项目中，20 个 task 的 subagent 全部一次完成，没有出现 BLOCKED 状态。最复杂的 task（Task 13 AgentRunner）也在一次 dispatch 中完成，尽管有 4 个 Important robustness 问题被标记为 hardening。

最优的 task 颗粒度是**"一个 subagent 一次会话内能完成的最小可测试单元"**。本项目的 20 个 task 大致分为三类：
- **数据/接口 task（Task 1-3）：** 100-150 行 brief，subagent 5-10 分钟完成。这是最优颗粒度。
- **机制 task（Task 9-11）：** 150-200 行 brief，subagent 10-15 分钟完成。反馈闭环的三个 task 颗粒度合适——每个 task 只负责一个阶段（解析/分类/决策）。
- **集成 task（Task 13, 16, 19）：** 200-300 行 brief，subagent 15-20 分钟完成。这些 task 涉及多文件协调，颗粒度偏大但可接受。

如果 task 颗粒度再大（如把 Task 9-11 合并为一个"反馈闭环"task），subagent 可能会在上下文中迷失；如果再小（如把 Task 1 的每个 dataclass 拆成独立 task），dispatch 开销会超过实现开销。

---

## 四、SPEC/PLAN 质量对实现质量的影响

### 具体案例：Task 3 ToolDispatcher 路由矛盾

SPEC §1 约定 ① 写道："ToolDispatcher 单点，内部顺序 guardrail.check → sandbox.execute"。但 PLAN Task 3 的参考代码中，ALLOW 分支调用 `sandbox.execute`，而测试的 FakeSandbox 不委托工具——它直接返回 `ActionResult(success=True, output="executed")`。测试期望 `output == "file content"`（FakeTool 的输出），这与实现矛盾。

**根因分析：** SPEC 的约定描述是正确的，但 PLAN 的参考代码在测试桩的设计上不够严谨——FakeSandbox 应该模拟真实 Sandbox 的工具委托行为，而不是返回硬编码值。

**影响：** subagent 在 TDD 的 RED 阶段就遇到了矛盾——测试期望 "file content" 但实现返回 "executed"。subagent 正确地选择了"以测试为准"并修改了实现，但这导致了一个架构偏离（ALLOW 分支直接调用 tool 而非 sandbox）。reviewer 发现了这个偏离并修复。

**教训：** SPEC 的描述质量决定了架构正确性，PLAN 的参考代码质量决定了实现效率。SPEC 写得再清楚，如果 PLAN 的参考代码有矛盾，subagent 仍然会偏离。这说明了 `writing-plans` 技能需要更强的自审——不能只检查"spec 覆盖完整"，还要检查"测试代码与实现代码是否自洽"。

---

## 五、最有效的 prompt/context 策略

### 策略 1: Task Brief 文件化

将每个 task 的全文从 PLAN.md 提取到独立的 brief 文件（`.superpowers/sdd/task-N-brief.md`），subagent 只读 brief 文件而非整个 PLAN.md。这减少了 subagent 的上下文负担，也防止了 subagent 被其他 task 的内容干扰。

### 策略 2: 跨 task 接口信息注入

在 dispatch prompt 中，除了 brief 文件路径，还注入了"这个 task 依赖哪些前置 task 的接口"的简短说明。例如 Task 3 的 dispatch 中写道："Tasks 1 (models) and 2 (LLM abstraction) are complete"。这让 subagent 知道哪些接口已存在，不需要重新定义。

### 策略 3: Reviewer 独立 dispatch

reviewer subagent 只收到 brief + report + diff，不收到 implementer 的 dispatch prompt。这保证了 reviewer 是独立评审，不会被 implementer 的上下文影响。

### 策略 4: System Prompt 迭代

在运行验证阶段，发现 LLM 一直重复 WriteFile 不提 Done。根因是 system prompt 没有明确告诉 LLM"任务完成后必须提 Done"。修复方法是在 system prompt 末尾加一句"CRITICAL: After completing the requested task, you MUST respond with Done to finish."。这说明 system prompt 的每一句话都会影响 LLM 的行为——模糊的指令会导致无限循环。

---

## 六、凭据与分发迫使我想清楚的问题

### 凭据

凭据要求（§3.1 + §4.2）迫使我想清楚了三个问题：

1. **密钥的生命周期：** 不仅仅是"存储"，还包括"首次引导录入（隐藏输入）"、"查看状态（不回显明文）"、"更新"、"清除"。CredentialStore 的五个方法（store_key/get_key/has_key/delete_key/status）正是这个生命周期的体现。

2. **多层回退的优先级：** keyring → env var → .env file。这不是随意排列——keyring 最安全（OS 级加密），env var 次之（进程可见），.env 最不安全（明文文件）。每一层都有不同的适用场景：本地开发用 keyring，云部署用 env var，CI 用 .env。

3. **密钥与 agent 工具环境的隔离：** Sandbox 的环境白名单只允许 PATH/HOME/LANG——密钥环境变量不会进入 agent 的工具执行环境。这意味着即使 agent 被 prompt injection 攻击，它也无法通过 `env` 命令读取密钥。

### 分发

分发要求（§3.2）迫使我想清楚了两个问题：

1. **"别人如何获取并运行"的工程问题：** Dockerfile 不仅仅是"打包代码"——它需要正确的构建顺序（COPY 在 pip install 之前）、依赖声明（pyproject.toml 的 [build-system]）、安全防护（.dockerignore 排除 .env）。

2. **key 在目标机的安全配置：** README 必须写清楚三种配置方式（keyring/env/.env）及其风险。Docker run 命令用 `-e HARNESS_API_KEY=...` 传入，不写入镜像。

---

## 七、如果重做我会改变什么

1. **PLAN 自审更严格：** 我会在 PLAN 自审中增加一项检查——"每个 task 的测试代码与实现代码是否自洽"。这能提前发现 Task 3 的路由矛盾和 Task 8 的死代码。

2. **冷启动验证更正式：** 虽然subagent-driven development 天然提供了冷启动验证，但我没有用"不同类型的智能体"来做正式的冷启动验证。如果重做，我会在 PLAN 完成后，用一个不同的 agent（如 Claude Code 或 Cursor）来试跑 1-2 个 task，记录它在哪里受阻。

3. **安全测试更全面：** 路径遍历防护只测了一个攻击向量（`../../../etc/passwd`）。如果重做，我会在 PLAN 中加入更多攻击向量（绝对路径、符号链接、UNC 路径、前缀混淆）。

4. **前端用 Open Design：** 通用要求 §3.6 推荐用 Open Design 进行界面开发。我用了原生 HTML/CSS/JS，功能可用但不够美观。如果重做，我会用 Open Design 提升前端质量。

5. **更早做运行验证：** 我在所有 20 个 task 完成后才做运行验证。如果重做，我会在 Task 14（RealLLMClient）完成后就做一次运行验证，提前发现 system prompt 的问题。

---

## 八、对 Superpowers 方法论的批判

### 它假设了什么

1. **假设 PLAN 的参考代码是自洽的。** 事实上，PLAN 的参考代码存在内部矛盾（Task 3 测试与实现矛盾、Task 8 死代码）。`writing-plans` 技能的自审只检查"spec 覆盖完整"和"无占位符"，不检查"测试代码与实现代码是否自洽"。

2. **假设 subagent 能处理所有异常情况。** 事实上，subagent 在遇到 PLAN 矛盾时会做出合理但不一定正确的选择（如 Task 3 绕过 sandbox）。这需要 reviewer 来纠正。

3. **假设 git worktree 是隔离的最佳方式。** 对于新项目，subagent 的独立 session 已经提供了足够的隔离。worktree 的价值在大型现有代码库中更高。

### 这些假设在我的项目里成立吗

1. **PLAN 自洽性假设：不成立。** 这是最关键的假设失效。subagent-driven development 的"每个 subagent 只看自己的 brief"设计放大了这个风险——subagent 无法发现跨 task 的矛盾。

2. **subagent 能力假设：基本成立。** 20 个 task 中只有 3 个需要 fix subagent 介入（Task 3/4/15），其余都是一次通过。但 fix 的原因都是 PLAN 参考代码的缺陷，而非 subagent 的能力不足。

3. **worktree 假设：不成立但无害。** 新项目不需要 worktree，但使用 worktree 也不会造成问题——只是增加了不必要的步骤。

### 总体评价

Superpowers 的核心洞察是正确的：**流程脚手架（TDD、评审、计划）在 AI 协作中容易松懈，需要强制执行**。subagent-driven development 的"fresh subagent per task + two-stage review"模式确实有效——它让 20 个 task 在一次 session 中连续完成，且每个 task 都经过了 spec 合规 + 代码质量双重评审。

但 Superpowers 的 `writing-plans` 技能需要更强的自审——特别是"测试代码与实现代码的自洽性检查"。这是整个流程中最薄弱的环节，也是 subagent 偏离的主要来源。
