# 修仙模式 Skill

把 WorkBuddy 的每一次使用变成一场修行：提问历练、完成任务悟道、调用 Skill 修习功法，累计修为沿 **七境二十一阶** 晋升；并含灵力石、天赋树、随机奖励、论道 PK（异步真实对手）、双表防篡改核算与美化洞府主页。

> 完整设计见配套《修仙模式需求文档 v2.0》。本文件为安装/使用/资源说明。

## 目录结构
```
xiuxian-skill/
├── SKILL.md                  # skill 定义与斜杠命令
├── README.md
├── assets/
│   ├── icons/                # 47 张图标（realm7/skill7/resource2/talent4/reward3/battle3/pet21）
│   ├── dongfu.html           # 洞府主页模板（render 时注入数据 + 图标 base64 内联）
│   └── pet.html              # 灵宠卡片模板
├── scripts/
│   ├── common.py             # 路径/配置/状态重建/境界/公式/校验码/工具
│   ├── reconcile.py          # 对账计分引擎
│   ├── auto_reconcile.py     # 自动结算（扫描 WorkBuddy 会话记录，零交互）
│   ├── sync_leaderboard.py   # 论道榜 upsert + 校验 + 候选读取 + 战报追加
│   ├── pk_engine.py          # 抽对手 + 五行克制结算 + 文字战报
│   ├── talent.py             # 天赋树解锁
│   ├── render_dongfu.py      # 生成洞府主页 HTML
│   ├── render_pet.py         # 生成灵宠卡片 HTML
│   ├── install_auto_reconcile.bat  # 一键注册自动结算计划任务（需管理员）
│   └── cli.py                # 命令分发入口
└── config/
    ├── thresholds.json       # 21 级阈值 + 评分初值 + PK/公式常量
    ├── skills_map.json       # Skill→功法系别映射 + 解锁境界
    ├── talents.json          # 天赋节点
    ├── rewards.json          # 随机奖励
    ├── holidays.json         # 中国法定节假日静态表（需年度更新）
    ├── secret.json           # 校验码盐值 SALT（设计决定：随代码分发，见"防伪造说明"）
    └── icons_manifest.json   # 图标 id→路径/中文标签
```

## 安装
1. 将本 skill 文件夹整体放入 WorkBuddy 的 skills 目录（用户级 `~/.workbuddy/skills/` 或项目级）。
2. 依赖：Python 3.10+（**仅标准库，无需 pip 安装**，腾讯在线后端为可选项）。
3. 首次使用执行 `python scripts/cli.py init <道号>` 建立修炼身份。

### 导入分发版（给其他智能体）
- 本仓库顶层目录名应为 `xiuxian`（与 `SKILL.md` 中 `name: xiuxian` 一致），解压/拷贝后即为 `~/.workbuddy/skills/xiuxian/`，WorkBuddy 重启或刷新技能列表后即可用 `/xiuxian` 调用。
- 无任何第三方依赖与网络要求：离线本地后端默认可用，全部数据落在用户级 `~/.workbuddy/xiuxian/`。
- 校验盐值 `SALT` 随代码分发（设计如此，属路线②「无后端·日志可溯」方案），导入方无需单独配置。
- 若导入方 WorkBuddy 用其他 Python 解释器，仅需保证 `python`/`python3` 指向 3.10+ 即可，脚本不依赖特定路径。

## 使用
在 WorkBuddy 输入 `/xiuxian 状态`、`/xiuxian 结算 --complex --files 2 --skill ImageGen`、`/xiuxian 论道` 等。
亦可直接命令行：`python scripts/cli.py <命令>`。

### 命令与别名
| 中文（斜杠） | 英文别名（cli） | 说明 |
|------|------|------|
| `/xiuxian 初始化 <道号>` | `init [--daohao 道号]` | 建立修炼身份（位置参数或 `--daohao` 均可） |
| `/xiuxian 状态` | `status` | 文字小结 + 渲染洞府主页 |
| `/xiuxian 结算` | `cultivate` | 记录修炼会话（`--complex`/`--files N`/`--skill NAME`） |
| `/xiuxian 论道` | `pk` | ⛔ 已暂停（同境真实对手条件未满足），恢复后支持 `演武`/`--opponent 道号` |
| `/xiuxian 天赋` | `talent` | 天赋树（`--list`/`--unlock ID`） |
| `/xiuxian 洞府` | `render` | 仅重渲染洞府主页 |
| `/xiuxian 宠物` | `pet` | 生成灵宠卡片（`--mood`/`--stage`） |
| `/xiuxian 同步` | `sync` | 同步论道榜主表 |
| `/xiuxian 快照` | `snapshot` | 每日快照 |
| `/xiuxian 校验` | `verify` | 自校验状态与重放一致性 |

### 自动结算（零交互，推荐）
- `scripts/auto_reconcile.py` 扫描 WorkBuddy 会话记录（`~/.workbuddy/projects/*/*.jsonl`），
  按天统计真实使用（提问/对话轮次/工具与 Skill 调用/文件产出）自动结算，**无需手动敲命令**。
- 每天最多结算一次（防刷）；`--preview` 干跑预览，`--commit` 实际结算。
- 一键启用：管理员运行 `scripts/install_auto_reconcile.bat`，注册每日 09:00 / 21:00 计划任务。

## 查看指标
- **洞府主页**：`/xiuxian` 或 `/xiuxian 洞府` 生成 `~/.workbuddy/xiuxian/dongfu.html`，双击浏览器打开（玻璃卡 + 环形进度 + 渐变趋势 + 功法图鉴，图标已内联）。
- **论道榜**：共享腾讯文档表（在线后端开启时）。

## 数据位置
- `~/.workbuddy/xiuxian/history.jsonl` —— 权威日志（唯一真相源）
- `~/.workbuddy/xiuxian/state.json` —— 缓存/镜像
- `~/.workbuddy/xiuxian/dongfu.html` —— 生成的洞府主页
- `~/.workbuddy/xiuxian/leaderboard.json` + `battles.jsonl` —— 本地后端数据

## 防伪造说明（路线②）
- `state.json` 由 `history.jsonl` 重放得出，改缓存不配套改日志即暴露。
- 校验码 `SHA256(SALT+字段)[:16]` 做粗筛；PK 时按相同规则重放对方日志挑战。
- 绝对不可伪造需受信任后端（规划中三期）。

## 在线后端（可选）
默认本地后端离线可用。若要接入已建好的腾讯文档主表：
- 设置环境变量 `XIUXIAN_TENCENT=1`
- 确保腾讯文档 CLI 存在：`~/.workbuddy/plugins/cache/workbuddy-builtin/tencent-docs-plugin/1.0.0/skills/tencent-docs/tencentdocs.py`
- 表：`修仙论道榜`(WhliUmAAkOJL) / `修仙论道战报表`(WjaLwseDyatk)
