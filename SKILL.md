---
name: xiuxian
title: 修仙模式
description: 把 WorkBuddy 使用变成一场修行——提问历练、完成任务悟道、调用 Skill 修习功法，累计修为沿七境二十一阶晋升；含灵力石、天赋树、随机奖励、论道 PK（异步真实对手）、双表防篡改核算与美化洞府主页。全程零交互自主运行。
type: normal
version: 2.0
commands:
  - name: 状态
    description: 打印文字修炼小结并渲染/打开洞府主页
  - name: 结算
    description: 手动记录一次修炼会话并结算计分（可带 --complex / --files N / --skill NAME）
  - name: 论道
    description: 触发一次论道 PK，输出文字战报（练气二层解锁）
  - name: 天赋
    description: 查看/解锁天赋树（--list / --unlock ID）
  - name: 洞府
    description: 仅重渲染洞府主页
  - name: 同步
    description: 将本机修炼数据同步至论道榜主表
---

# 修仙模式 Skill

将每一次使用 WorkBuddy 视为一次修行：提问是历练、完成任务是悟道、调用 Skill 是修习功法、完成复杂任务是闭关突破。系统自动记录行为、累计「修为值」，沿境界阶梯晋升，把工具使用变成有养成感的长期修行。

## 核心理念
- **全程零交互自主运行**：升级、突破、掉落、解锁均按规则静默执行。
- **正向体验**：不掉分、只做温和提醒。
- **真实可对比**：PK 接入共享榜真实数据（非纯虚拟对手）。

## 用法（斜杠命令）
> 在 WorkBuddy 聊天框输入 `/xiuxian <命令>` 即可。

| 命令 | 作用 |
|------|------|
| `/xiuxian` 或 `/xiuxian 状态` | 打印文字小结 + 渲染并打开洞府主页 |
| `/xiuxian 结算 [--complex] [--files N] [--skill NAME]` | 记录一次修炼会话并结算计分 |
| `/xiuxian 论道 [对手道号]` | ⛔ 论道 PK 已暂停（同境真实对手条件未满足），暂不可用 |
| `/xiuxian 天赋 [--list \| --unlock ID]` | 查看或消耗灵力石解锁天赋 |
| `/xiuxian 洞府` | 仅重渲染并打开洞府主页 |
| `/xiuxian 宠物` | 渲染带 CSS 动画的灵宠卡片（境界进化形态 + 心情系统） |
| `/xiuxian 同步` | 将本机数据 upsert 到论道榜主表 |
| `/xiuxian 校验` | 自校验状态与重放一致性 |

> 中英文命令等价：`状态/status`、`结算/cultivate`、`论道/pk（已暂停）`、`天赋/talent`、`洞府/render`、`宠物/pet`、`同步/sync`、`校验/verify`、`初始化/init`、`快照/snapshot`。
> `初始化` 支持位置参数道号或 `--daohao 道号`；`论道` 目前暂停，恢复后支持 `演武`（或 `--mode 演武`）强制本地演武，或 `--opponent <道号>` 指定真实对手；`宠物` 支持 `--mood <修炼中|论道胜|论道负|打盹|悠闲>` 预览指定心情。

### 结算参数说明
- `--complex`：标记为复杂多轮任务（更高计分 + 闭关突破分）。
- `--files N`：本次产出的实体文件数（每个 +20，封顶 3 个）。
- `--skill NAME`：本次调用/习练的 Skill 名称（归入对应功法、+熟练度、+修为）。

示例：`/xiuxian 结算 --complex --files 2 --skill ImageGen`

### 自动结算（零交互）
- 已提供 `scripts/auto_reconcile.py`：扫描 WorkBuddy 会话记录（`~/.workbuddy/projects/*/*.jsonl`），
  按天统计真实使用（提问/对话轮次/工具与 Skill 调用/文件产出）自动结算，无需手动敲命令。
- 每天最多结算一次；`--preview` 干跑预览，`--commit` 实际结算。
- 一键注册计划任务（每天 09:00 / 21:00 自动运行）：右键管理员运行
  `install_auto_reconcile.bat`（在 `_asar_build` 目录），或手动 `schtasks` 创建。

## 查看指标的 4 个出口
1. **本地洞府主页**（`~/.workbuddy/xiuxian/dongfu.html`，由 `状态`/`洞府` 生成，双击即可看）。
2. **会话内文字小结**（`状态` 命令）。
3. **腾讯文档论道榜**（共享表，看全网排名）。
4. **终端**：`python scripts/cli.py status`。

## 境界与计分（摘要）
- 七境 × 三小阶 = 21 级；练气二层解锁论道。
- 计分维度：提问 / 完成任务 / 调用 Skill / 连续活跃（道心）/ 闭关突破。
- 灵力石：夜间与法定节假日掉落，用于解锁天赋。
- 总修仙分值 = 修为 + 灵力石×0.5 + 功法熟练度和×10 + 胜×20 − 负×5 + 连续活跃×3（含上限）。

详细设计见《修仙模式需求文档》（配套交付物）。

## 数据与安全
- 权威数据源为 `~/.workbuddy/xiuxian/history.jsonl`，`state.json` 为其缓存/镜像。
- 防伪造采用「行为日志为唯一真相源 + 日志链校验」（路线②）：校验码粗筛 + PK 时日志重放挑战，使伪造可检测、可追溯、不可抵赖，对休闲玩法足够；绝对防伪需受信任后端（规划中）。
- 同步默认使用本地后端（离线可用）；设置 `XIUXIAN_TENCENT=1` 且腾讯文档 CLI 可用时切换在线主表。
