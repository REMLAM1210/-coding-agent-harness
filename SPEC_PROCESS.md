# SPEC_PROCESS.md — 规约与计划生成过程

## 一、Brainstorming 关键节点

### 1.1 初始意图与智能体追问

项目启动时，我向智能体表达了"构建一个 Coding Agent Harness"的模糊意图。智能体通过 `brainstorming` 技能主动追问了以下关键问题：

**Q1: 你想聚焦哪个维度？**
> 智能体列出了六个候选维度（决策、工具、记忆、治理、反馈、配置），并建议选择 1-2 个做深。
> **我的决策：** 选择"反馈闭环（Feedback Loop）"作为主角维度。理由是这个维度最能体现工程深度——不是简单调用 LLM，而是构建一个能感知失败、分类失败、决定重试策略的闭环系统。

**Q2: 用什么语言和目标项目类型？**
> **我的决策：** Python 3.11+，目标项目为 Python（pytest/ruff/mypy）。理由：Python 生态与课程内容契合，且 pytest/ruff/mypy 的输出格式明确，便于解析。

**Q3: LLM 供应商？**
> **我的决策：** NJU endpoint（`https://njusehub.info/v1`，OpenAI 兼容）。理由：课程提供，免费额度，且 OpenAI 兼容接口意味着抽象层可保持供应商无关。

**Q4: 架构形态？**
> 智能体提出了三种方案（A: Web-first / B: CLI-first / C: Library-first）。我最初选了 C，但智能体追问"通用要求 §4.11 要求线上部署 WebUI"，促使我改选 **A: Web-first**。这是一个智能体追问让我修正原设想的典型案例。

### 1.2 设计分节呈现与签字确认

智能体将设计分为 §1-§10 共十节，逐节呈现并要求确认。关键的设计决策包括：

- **§1 三条架构约定：** ① ToolDispatcher 单点（guardrail.check → sandbox.execute）；② RawExecutionResult 作为 feedback_tools 与 validators 之间的显式契约；③ SessionRegistry 属于 webui 层，kernel 只暴露 EventSink 接口。这三条约定是智能体提出的，我全部采纳，因为它们有效隔离了关注点。
- **§4 反馈闭环深度：** 智能体提出跨轮次失败集合比较（收敛/停滞/振荡检测），这超出了我最初的设想。我采纳并要求加入停滞和振荡的提前升级逻辑。
- **§5 安全五原则：** 智能体提出了"密钥永不进入 agent 工具环境"这一原则，我补充了"密钥访问由 Harness 而非 LLM 控制"。

---

## 二、三轮关键迭代

### 迭代 1: SPEC 初稿 → 自审

SPEC.md 初稿 609 行，涵盖所有 §4.2 要求的章节。智能体自审通过（无占位符、无矛盾、无歧义、无范围问题）。

### 迭代 2: 用户评审 → 14 项修改

我对 SPEC 初稿进行了详细评审，提出 14 项修改意见：

**🔴 必须修复（4 项）：**
1. **ToolDispatcher 架构约定不完整** — 初稿未明确 ALLOW 分支必须经过 sandbox.execute，而非直接调用 tool。修复：在 §1 约定 ① 中补充"内部顺序 guardrail.check → sandbox.execute，工具不做自己的 guardrail 检查"。
2. **RawExecutionResult 契约缺失** — 初稿未将 RawExecutionResult 定义为 feedback_tools 与 validators 之间的显式数据契约。修复：在 §1 约定 ② 中补充，并在数据模型中定义。
3. **SessionRegistry 归属不明** — 初稿未明确 SessionRegistry 属于哪一层。修复：在 §1 约定 ③ 中明确"属于 webui 层，kernel 只暴露 EventSink 接口"。
4. **HITL 超时语义不清** — 初稿未说明 TIMEOUT 如何复用 DENY 逻辑。修复：在 §4 约定 ③ 中明确"TIMEOUT 复用 DENY 逻辑（reason='approval_timeout'）+ 清理"。

**🟡 建议改进（10 项）：**
5. 跨轮次失败集合比较的具体算法（收敛/停滞/振荡的判定条件）
6. 失败类别优先级排序的完整定义
7. REVERT 策略标记为 stretch goal
8. ESCALATE 全自动、ABORT 可选转 HITL 的语义
9. Sandbox 环境白名单用白名单而非黑名单
10. ToolDispatcher 三分支（ALLOW/DENY/REQUIRE_APPROVAL）的完整定义
11. 凭据隔离归属 Governance 机制
12. 上下文构造的具体策略（历史截断、反馈格式化、记忆自动检索）
13. 停止条件的完整定义（LLM Done + 自动停止 + 最大迭代次数）
14. RealLLMClient 的系统提示骨架 + JSON schema + 解析错误回灌

修复后 SPEC.md 增至 827 行，我确认通过。

### 迭代 3: PLAN 生成 → 自审 → 执行

`writing-plans` 技能将 SPEC 分解为 20 个 TDD task，每个 task 包含完整的测试代码和实现代码。PLAN.md 自审通过（spec 覆盖完整、无占位符、类型一致）。

---

## 三、AI 提出而我采纳的建议

| 建议 | 来源 | 我的决策 |
|---|---|---|
| 三条架构约定（单点分发、RawExecutionResult 契约、SessionRegistry 归属） | 智能体 §1 | ✅ 采纳，成为项目核心设计 |
| 跨轮次失败集合比较（停滞/振荡检测） | 智能体 §4 | ✅ 采纳，成为反馈闭环的核心深度 |
| 安全五原则 | 智能体 §4.2 | ✅ 采纳，并补充"密钥访问由 Harness 控制" |
| Web-first 架构 | 智能体追问 | ✅ 采纳，修正了我最初选的 Library-first |
| 失败类别优先级排序 | 智能体 §3.5.2 | ✅ 采纳，COLLECTION_ERROR > TIMEOUT > TYPE_ERROR > ASSERTION_FAILURE > LINT_VIOLATION |

## 四、我推翻或修正的 AI 建议

| 建议 | 我的决策 | 理由 |
|---|---|---|
| 初始架构选 Library-first | 改为 Web-first | 通用要求 §4.11 要求线上部署 WebUI |
| REVERT 策略完整实现 | 标记为 stretch goal | 工作量过大，优先保证 RETRY_SAME/ESCALATE/ABORT |
| .env 文件作为凭据存储首选 | 降级为第三优先级（keyring → env → .env） | .env 是明文，安全性最低 |

---

## 五、冷启动验证（§4.5）

### 5.1 方法论说明

通用要求 §4.5 要求用"与主开发智能体不同的 agent"在"不提供对话历史"的前提下，仅凭 SPEC + PLAN 尝试实现 1-2 个 task。

本项目的 subagent-driven development 工作流天然满足这一要求：每个 task 派发的 subagent 都是**全新 session**，不继承任何先前对话历史，仅接收 task brief（从 PLAN.md 提取的 task 全文）+ 必要的跨 task 接口信息。这与 §4.5 的要求高度吻合。

### 5.2 冷启动暴露的 SPEC/PLAN 缺陷

在 subagent 执行过程中，以下问题被暴露：

**缺陷 1: ToolDispatcher ALLOW 分支路由不一致（Task 3）**
- **现象：** subagent 发现 PLAN 的测试代码期望 `output == "file content"`（FakeTool 的输出），但 PLAN 的实现代码调用 `sandbox.execute`（FakeSandbox 返回 `"executed"`）。测试与实现矛盾。
- **根因：** PLAN 的 FakeSandbox 是一个不委托工具的桩，而真实 Sandbox 会委托工具。测试的 FakeSandbox 应该模拟真实行为。
- **修复：** 让 FakeSandbox 接受 tools 参数并委托；恢复 ALLOW 分支调用 `sandbox.execute`。
- **spec 影响：** 暴露了 SPEC §1 约定 ① 的描述不够明确——需要强调"工具不做自己的 guardrail 检查"且"sandbox 拥有工具路由职责"。

**缺陷 2: 路径遍历防护不完整（Task 4）**
- **现象：** subagent 发现 `ListFilesTool` 完全没有路径遍历防护；`_resolve_safe` 的 `startswith` 检查可被前缀混淆攻击（`/tmp/foo` vs `/tmp/foobar`）。
- **根因：** PLAN 的参考代码只用了 `startswith`，未考虑前缀混淆；`ListFilesTool` 遗漏了过滤。
- **修复：** 改用 `os.path.commonpath`；`ListFilesTool` 过滤 glob 结果。
- **spec 影响：** 暴露了 SPEC §3.4.2 对路径遍历防护的描述不够具体——应明确要求 component-wise 比较。

**缺陷 3: HITL 状态机存在死代码（Task 8）**
- **现象：** subagent 发现 `else`/TIMEOUT 分支不可达——`DecisionType` 只有 ALLOW/DENY/REQUIRE_APPROVAL，超时被建模为 DENY + reason="approval_timeout"，走的是 `elif DENY` 分支。
- **根因：** PLAN 的参考代码与 SPEC §4 约定 ③ 矛盾——约定说"TIMEOUT 复用 DENY 逻辑"，但代码写了一个独立的 else 分支。
- **修复：** 删除 else 分支。
- **spec 影响：** 暴露了 SPEC §4 约定 ③ 的描述与 PLAN 参考代码不一致。

**缺陷 4: CredentialStore None-backend 崩溃（Task 15）**
- **现象：** subagent 发现当 keyring 未安装时，`get_key()` 在到达 env 回退之前就崩溃（`AttributeError: NoneType has no attribute 'get_password'`）。
- **根因：** PLAN 的参考代码没有对 None backend 做防护。
- **修复：** 所有 backend 调用前加 `if self._backend is not None:` 守卫。
- **spec 影响：** 暴露了 SPEC §7.1 对 keyring 缺失场景的描述不够具体——应明确要求 None-backend 守卫。

### 5.3 冷启动验证结论

subagent-driven development 过程作为冷启动验证，暴露了 4 个 SPEC/PLAN 缺陷，全部在 task 执行过程中修复。这证明了 §4.5 的核心论点：**一个全新的 agent 会在你未明文写下的每个假设处受阻**。最典型的案例是 Task 3 的 ToolDispatcher 路由矛盾——这个矛盾在 SPEC 自审和 PLAN 自审中都没有被发现，但 subagent 在实际编写测试时立刻暴露了它。

---

## 六、Brainstorming 技能反思

### 做得好的地方
- **分节呈现 + 逐节确认** 的模式有效防止了"一次性大文档"的审阅疲劳。
- **主动追问**（如"通用要求要求线上部署 WebUI"）让我修正了不合理的架构选择。
- **三条架构约定**的提出体现了智能体对关注点分离的深刻理解。

### 让我不满的地方
- **SPEC 自审不够严格** — 智能体自审通过了，但我手动评审发现了 14 项问题。说明自审不能替代人工评审。
- **PLAN 参考代码存在内部矛盾** — Task 3 的测试与实现矛盾、Task 8 的死代码，都是 PLAN 自审应该发现但未发现的。
- **对安全细节的描述不够具体** — 路径遍历防护只说了"有防护"但没说用什么算法；keyring 缺失场景只说了"有回退"但没说怎么守卫。
