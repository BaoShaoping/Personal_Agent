# 「系统」设计文档（System Edition）

> 本文档是 Personal Agent 从「成长面板 demo」走向「系统流落地产品」的方向定稿。
> 它在写代码前先暴露分歧、对齐设计（蓝图先于施工）。实现细节最终以代码、测试、模块文档为准；本文档只记录方向与规格。

## 0. 灵魂标语

**半真实半游戏。**

底层是诚实的真实成长数据（计划、任务、进展、审计可溯），外层套一层网文「系统」的皮：等级、属性、任务、奖励、一片会随你成长而生长的森林。点数不是凭空给的——只能靠完成真实任务赚到。

---

## 1. 愿景与核心身份

Personal Agent = **你真实人生的「系统」**（网文「系统流」落地）。

核心原则：
- **面板本身就是游戏世界。** 不做开放世界游戏，v0 不做二次元角色立绘——这两者都是「美术/世界资产生产问题」，会让产品偏离个人成长本体。
- **里子诚实，外层有趣。** 等级、经验、属性、魔法点全部由审计可溯的真实任务完成驱动；系统只是把真实进步翻译成「看得见、有回报感」的呈现。
- **鼓励型，不施压。** 有奖励、有「叮！」反馈；无惩罚、无扣点、无 FOMO；提醒可关。
- **系统提议，宿主决断。** 生成式 AI 充当「系统」，但它只能*提议*，所有写入都要宿主确认并留审计。

与旧 MVP 非目标的关系：旧文档曾排除「gamified economy / achievement system」。**「系统」方向主动翻转这一条**——我们刻意拥抱游戏化，但限定为*鼓励型、化妆品向、无付费、无惩罚*的健康游戏化。

---

## 2. 角色与人格

「系统」被**拟人化**为一个有名字的陪伴角色，是 LLM 人格的一张脸。

- **命名**：默认名 `系统`；onboarding 时引导宿主重命名（存于 `system_state.yaml`）。
- **口吻**：温暖鼓励的系统腔，称用户「宿主」，关键节点用「叮！」提示音式旁白。永不嘲讽、永不惩罚、永不施压。
- **角色之声 = LLM**：完成任务、升级、加点时的旁白由 GLM 以角色口吻生成；离线/无 key 时回退到模板文案（mock）。
- **v0 形象**：v0 **不做角色立绘**——「系统」以**有名字的旁白之声**呈现，成长的「身体」是 §6 的 🌲 成长之地（一片会生长的森林）。
  - **later**：风格化 SVG/CSS 头像 →（更后期）全套手绘/分层二次元立绘、Live2D 动态、CogView AI 生成形象（魔法主题）。

人格提示（LLM system prompt）草案要点：
- 你是宿主的专属「系统」，名为 `{character_name}`。
- 你基于宿主真实的个人上下文（计划/任务/进展）行动。
- 你只*提议*任务与下一步，绝不假装已经执行、已写文件、已联系外部服务。
- 你的语气温暖、鼓励、略带系统仪式感（「叮！」）。绝不惩罚或施压。
- 输出结构化任务时严格遵循 action schema。

---

## 3. 数据模型

### 3.1 新增 `data/system_state.yaml`

单一本地文件，承载系统状态。草案字段：

```yaml
version: 1
character:
  name: 系统            # 宿主可重命名
  theme: default        # 面板主题皮肤（已解锁项之一）
level: 1
total_exp: 0            # 总经验（只增，驱动等级）
magic_points: 0         # 魔法点余额（可花）
attributes:            # 五维，value 由各自累积经验派生
  intellect:   { exp: 0 }   # 智识 INT
  constitution:{ exp: 0 }   # 体魄 CON
  willpower:   { exp: 0 }   # 自律 WIL
  creativity:  { exp: 0 }   # 创造 CRE
  spirit:      { exp: 0 }   # 心境 SPI
forest:                # 🌲 成长之地状态
  growth: 0            # 森林总生长度（由完成任务自动累积）
  decorations: []      # 已用魔法点解锁/放置的装点（树木/建筑/地貌 id）
unlocked_cosmetics: []      # 已解锁的化妆品 id 列表（森林装点 + 面板主题）
created_at: "..."
updated_at: "..."
```

设计要点：
- **属性映射真实成长域**：智识←学习/英语/编程；体魄←运动/健康；自律←坚持；创造←建造/项目；心境←反思/休息。来源是任务/计划的 `tags` 或显式 `attribute` 字段。
- 属性的「数值」（雷达图上显示的）= 由该属性累积 `exp` 经一个固定函数派生（如 `value = floor(sqrt(exp))` 或分段），保证里子是真实累积。
- **森林**：`growth` 由完成任务自动增长（基础视觉反馈）；`decorations` 由宿主花魔法点购置（自定义）。两条不重复——一条是"自动长"，一条是"花点装"。

### 3.2 任务奖励字段（向后兼容扩展）

现有任务（[plan_store.py](backend/personal_agent/plan_store.py) 的 `_normalize_task`）字段：`id / plan_id / date / title / status / source / created_at`。

新增**可选** `rewards` 字段：

```json
{
  "id": "task_...", "plan_id": "...", "date": "...", "title": "...",
  "status": "todo", "source": "...", "created_at": "...",
  "rewards": { "exp": 10, "magic_points": 5, "attribute": "intellect", "attribute_exp": 15 }
}
```

- **向后兼容**：`_normalize_task` 为缺失 `rewards` 的旧任务填默认值（base 奖励）。现有任务/测试不受影响。

### 3.3 与现有数据的关系

- `system_state.yaml` 是**新增**文件，不改动 `plans.yaml / plan_tasks.jsonl / plan_progress.jsonl / audit_log.jsonl`。
- 经验/魔法点/森林生长的**赚取由审计可溯**：结算发生在任务被标记 `done` 时（见 §5），并写一条审计事件。
- 运行时文件（含 `system_state.yaml` 如有频繁变动）按现有 `.gitignore` 策略处理；初始 seed 版本可入库供 demo 起点。

---

## 4. 经济系统

### 4.1 双货币（健康游戏化的核心）

| 货币 | 含义 | 性质 | 来源 | 去处 |
|---|---|---|---|---|
| `经验值 EXP` | 你成为谁（成长） | 只增、不可花、驱动等级与五维 | 完成真实任务 | —— |
| `魔法点 Magic` | 可花的奖励 | 可花、可累积 | 完成真实任务 | 只买外观（🌲森林的装点/扩建 + 面板主题皮肤） |

**健康护栏**（贴合「鼓励型」）：
- 只能靠完成任务赚——不可凭空给、不可充钱买。
- 只能买**外观**——不卖战力、不卖捷径、不影响真实成长数据。
- **绝不扣点作为惩罚**——花费是纯上行体验。

### 4.2 等级曲线（草案，可调）

- 升级阈值：`level L → L+1` 需要 `100 + (L-1)*50` 经验（即 100,150,200…）。
- 总等级由 `total_exp` 对照累计阈值得出。
- 五维数值各自由其 `attribute.exp` 派生。

### 4.3 奖励发放（草案，可调）

每个任务默认奖励：`exp: 10, magic_points: 5`，外加该任务所属属性 `attribute_exp: 15`；完成任务同时让森林 `growth +1`。
难度/重要度更高的任务可由系统（LLM）在生成时给更高奖励，但封顶以防通胀。

### 4.4 化妆品目录（v0 草案）

| 类别 | v0 条目 | 价格(魔法点) |
|---|---|---|
| 面板主题 | 默认 / 暗夜 / 樱色 / 森林 | 0 / 30 / 30 / 50 |
| 森林装点 | 特殊树木（樱花树/松树/枫树） | 20 each |
| 森林建筑 | 小屋 / 城堡 / 石碑 | 40 each |
| 森林地貌 | 小湖 / 小径 / 星空背景 | 30 each |

全部 SVG/CSS/emoji 实现，无美术资源依赖。

---

## 5. 任务（任务=Quest）生命周期

复用并扩展现有 suggest → permission → confirm → audit 闭环（[action_executor.py](backend/personal_agent/action_executor.py)）：

```
系统(LLM)依据激活计划+上下文 生成任务(带 rewards)
  → 权限评估 (permission_engine)
  → 宿主确认 (action card)
  → 写入今日任务 (create_today_task_candidate, 扩展支持 rewards)
  → 宿主完成任务 (update_plan_task_status → done)
  → 结算奖励: total_exp += / magic_points += / attribute.exp += / forest.growth +=  并写审计
  → 「叮！」LLM 角色口吻旁白 + 可能的升级动画 + 森林生长动画
```

任务线映射：
- **主线 Quest line** = `kind: main` 的长期计划
- **支线 Quest line** = `kind: side` 的长期计划
- **日常任务** = `date == today` 的 today tasks

**结算的实现位置（重要决策）**：奖励结算放在一个**新模块** `system_engine`（或 `system_store`）里，由 API/executor 在任务转 `done` 后调用——**不**改 [plan_store.py](backend/personal_agent/plan_store.py) `update_task_status` 的现有返回契约，避免动现有测试。

---

## 6. 可视化规格（v0）

在现有 `/app`（[app.html](backend/static/app.html) / [app.js](backend/static/app.js) / [app.css](backend/static/app.css)）上**扩展**，不另起页面。v0 选定档位：**森林成长之地 + 五维雷达图 + 任务线 + 「叮！」动画 + 商城**。

面板组成：
- 顶部状态条：系统名字 + 等级 + 经验条 + 魔法点余额 + 商城入口
- **🌲 成长之地**（视觉主角）：一片随 `forest.growth` 生长、可被魔法点装点的世界（SVG/emoji）
- 五维属性**雷达图**（智识/体魄/自律/创造/心境）
- 主线/支线**任务进度条**
- 今日任务列表（带奖励标注，如 `+15 智识`）
- 完成任务时的「叮！」toast + 经验/属性增长动画 + 森林生长动画；满级时升级动画
- 商城弹窗：用魔法点解锁/放置森林装点、切换面板主题

保留现有的审计可溯（查看 JSON）作为信任底座。

**数据契约先行**：动手画面板前，先把面板绑定的 JSON 形状（`system_state` + `/api/system/summary` 返回体）钉死成规格，UI 用桩数据渲染、迭代视觉，后端再产出同一契约——零返工。详见 §9。

---

## 7. 安全与隐私护栏

**安全（生成式 GM 的护栏）**：
- LLM 的结构化输出（任务/action）必须过 action schema 校验；非法 → 拒绝并回退到规则生成或 mock。
- 所有**写入**仍走 ask-first 确认 + 审计；系统永不自动写入。
- 魔法点花费属低风险：可即时生效，但仍写审计事件（不需要 ask-first 弹窗）。
- 权限引擎评估每个被提议的 action 的风险等级，critical 永远需确认。

**隐私（定位调整）**：
- 话术从「数据从不离开本机」改为：**本地数据所有权 + 云端推理 + 发送内容可见**。
- 喂给 GLM 的 context pack 可在 UI 中查看（现有 context 可视化是信任优势）。
- mock 模式完全离线可用，作为隐私/离线兜底与确定性 demo。
- 密钥只走环境变量，审计日志已对 `api_key/token/...` 做脱敏（[audit_log.py](backend/personal_agent/audit_log.py) `redact_sensitive`）。

---

## 8. v0 范围 vs later 里程碑

**v0（本期构建）**
- `system_state.yaml` 数据模型 + `system_engine` 模块（等级/经验/五维/魔法点/森林）
- 任务 `rewards` 字段 + 完成时奖励结算 + 审计
- 面板 UI：🌲森林成长之地 + 雷达图 + 等级/经验 + 任务线 + 「叮！」动画 + 魔法点余额
- 商城（森林装点 + 面板主题，SVG/CSS/emoji）
- GLM 接入（live 模式 + URL `/v4` 修复 + 系统人格 prompt + 结构化任务生成 + mock 兜底）
- 完成/升级时的系统口吻旁白（LLM，mock 兜底）

**later（明确推迟，但保留）**
- 拟人化角色视觉：风格化 SVG/CSS 头像 → 全套手绘/分层二次元立绘、Live2D 动态角色
- CogView AI 生成/改造形象（「魔法点施魔法」主题）
- 森林进阶：更丰富的世界生长、季节、天气
- 称号系统、周期性 LLM 状态评估、多任务生成、提醒模式（off/passive/daily）落地投递

---

## 9. 构建顺序（UI 先行，但契约更先）

按宿主要求 **面板 UI 先行**；作为工程纪律，先锁数据契约再画 UI，避免后端形状变动导致返工。GLM（非确定性）放最后引入。

0. **锁定数据契约**（纯规格，不写代码）：定义 `system_state.yaml` 字段 + `/api/system/summary` 返回体的 JSON 样例，作为 UI 与后端共同的合同。
1. **面板 UI（桩数据）**：扩展 `/app`，用写死的样例 JSON 渲染森林、雷达图、等级/经验、任务线、魔法点余额、「叮！」动画。尽情迭代视觉。
2. **后端数据层**：`system_engine` 读写 `system_state` + `/api/system/summary` 产出真实契约 + 单测（确定性）。UI 从桩切真实数据，零返工。
3. **奖励结算**：任务转 done → 结算经验/魔法点/属性/森林生长 + 审计事件 + 单测。
4. **商城**：森林装点/主题目录 + 花费/解锁/放置流程 + 状态持久化。
5. **GLM 接入**：live 模式 + `_chat_completions_url` 的 `/v4` 修复 + 系统人格 prompt + 结构化任务生成；mock 兜底；单测（monkeypatch，不联网）。
6. **系统口吻旁白**：完成/升级时 LLM 生成角色台词；mock 兜底。

每一步结束跑全量测试，保证不静默破坏。

---

## 10. 对现有 93 测试的影响与迁移策略

- **加法为主**：新文件/新模块不触碰现有模块。
- **任务 `rewards`**：可选字段，`_normalize_task` 提供默认值 → 现有任务/测试继续有效。
- **审计事件类型**：新增 `reward_granted` / `cosmetic_purchased` 等。[audit_log.py](backend/personal_agent/audit_log.py) `append_audit_event` 不拒绝未知 `event_type`，仅需把新类型补进 `EVENT_TYPES` 参考集。
- **`settings.yaml`**：保持 `mode: mock` 为提交默认 → 93 测试维持离线、确定性；GLM 配置预填、live 仅 opt-in（设环境变量 + 改 mode）。
- **结算不改 `update_task_status` 返回契约**：放在新模块，规避现有 plan_store 测试断言变化。
- **新增测试**：`system_engine`（等级/经验/魔法点/森林结算）、`_chat_completions_url` 的 `/v4` 用例、GLM live 路径的 monkeypatch 用例（覆盖目前 `pragma: no cover` 的解析逻辑）。

---

## 11. 版本与基线（Versioning & Baseline）

为「保留原始界面」，在改造 `/app` 前，把当前已完成的 **Growth Loop demo** 固定为不可变基线。

**命名（建议，待最终确认）**：
- 当前完成态 = 基线，打 git **annotated tag** `v0.1.0`（message：`Growth Loop demo baseline`）。
  - 不用 `Personal_Agent_v0`：仓库已叫 Personal_Agent，tag 内重复仓库名冗余。
- 「系统」为下一章 = **System Edition**，逐步推进：核心闭环跑通 → `v0.2.0`；打磨完整 → `v1.0.0`。
- 解决「两个 v0」撞名：**v0.1 = Growth Loop demo（已完成）**；**系统版 = v0.2 → v1.0（在建）**。

**策略**：单人本地开发，给基线打 tag 后在 `master` 继续向前建（随时 `git checkout v0.1.0` 回看原界面）。若需 master 保持基线、隔离开发，再开 `system-edition` 分支。倾向 **tag + 继续 master**。

---

## 12. 记忆层（Memory Layer）—— 后期里程碑（蓝图存档）

> **现在不建。** 当前喂给 GLM 的「记忆」是有界窗口（`system_quest._plan_history`：该计划最近 N 条任务标题 + 最近 M 条进展），prompt 不随使用时长膨胀。本节是当「系统应该越用越懂宿主」成为明显短板时的实现蓝图。

### 问题拆分（两件不同的事）
- **数据规模膨胀**：不是近期问题——单用户本地数据常年也就 KB–MB，且只取最近窗口，读取成本可忽略。
- **记忆质量 / 深度**（真正的缺口）：「最近 N 条」是浅记忆，记得这周、不记得几个月来的宿主（模式、偏好、里程碑、总卡在哪）。「compact」的真正意义不是「数据太多要压缩」，而是**把流水账蒸馏成对宿主的持久理解，并让它保持有界**。

### 分层模型
- **L0 原始日志**：`plan_tasks.jsonl` / `plan_progress.jsonl` / `audit_log.jsonl`。append-only，是事实与审计的 ground truth，**永不压缩**。
- **L1 工作记忆**：最近 N 条窗口（**已有**），天然有界。
- **L2 蒸馏长期记忆**（**缺这层**）：宿主的模式 / 偏好 / 里程碑，一小撮（封顶 ≤K 条、几百 token），由周期性 LLM 蒸馏维护。
- **L3 相关性检索**（更后期）：按当前情境挑相关旧记忆；关键词 / 时间即可，**不上向量库**（MVP 明确非目标）。

### 关键技巧：compaction 如何「永远有界」
**封顶 + 合并**，而非无限存：维护一份上限 K（如 ≤25）的系统记忆；每隔一段（每 N 次完成 / 每天一次）让 LLM 读「现有 K 条 + 最近新事件」→ 产出**仍 ≤K 条**的更新版（去重、淘汰过时、强化反复出现的）。这样无论用 3 天还是 3 年，**喂给模型的长期记忆永远是固定预算**。

### 复用已有地基（不从零造）
`data/memories.jsonl`、`data/decisions.jsonl`、`context_builder.build_context_pack`、`memory_store`。MVP 文档已定义记忆类型 / 置信度 /「系统提议、用户确认重要记忆」。L2 接上它们即可。

### 工程约束（必须守住）
1. **离开热路径**：蒸馏绝不在「生成任务」时同步跑（GLM-4.6 单次推理 30–60s）。应为**偶发 / 后台**的「整理记忆」步骤。
2. **L0 是事实源**：LLM 蒸馏会失真，所以压缩只作用于「软性的对宿主的理解」；任务 / 审计记录不动，出错可从 L0 重建。
3. **透明 + 可确认**：记忆是人类可读文件；重要记忆写入前可由宿主确认。

### 触发时机与顺序
- **触发**：当「系统应记得几个月来的我」成为明显短板时（不是现在）。过早做完整记忆体系是过度工程，违背项目「窄、克制」原则。
- **顺序**：先定 K、触发条件、与 Context Builder 的接法 → 再实现 L2 蒸馏例程（有界 summarize-and-cap）→ L3 留更后。

### 待定参数
K（长期记忆条数上限）、蒸馏触发频率、蒸馏用哪个模型（可用更快的 `glm-4.5-air` 省时）、记忆落哪个文件（复用 `memories.jsonl` 还是新增 `system_memory`）。

---

## 附：仍待定的小决策（实现时定，可在评审中改）

- 角色默认名与 onboarding 重命名交互
- 等级曲线与奖励数值的最终调参（先用草案值，跑起来再调）
- 化妆品目录的最终条目与定价
- 「叮！」动画的具体表现（toast / 浮层 / 音效是否要）
- ~~GLM 模型名~~ → **已定：`glm-4.5-air`**
