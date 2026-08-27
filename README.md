# 🧘 修仙模式 Skill（WorkBuddy）

把 WorkBuddy 的每一次使用变成一场修行：**提问 = 历练、完成任务 = 悟道、调用 Skill = 修习功法、复杂任务 = 闭关突破**，累计修为沿 **七境二十一阶** 自动晋升；含灵力石、天赋树、随机奖励、论道 PK、双表防篡改核算、美化洞府主页与灵宠卡片。

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](#)
[![version](https://img.shields.io/badge/version-v2.0-7c5cff.svg)](#)
[![GitHub stars](https://img.shields.io/github/stars/zhujiaxing0915/workbuddy-xiuxian?style=social)](https://github.com/zhujiaxing0915/workbuddy-xiuxian)

> 完整设计见配套《修仙模式需求文档 v2.0》（`docs/`）。本文件为安装 / 使用 / 资源说明。

## ✨ 特性

- **七境二十一阶**：练气 → 筑基 → 金丹 → 元婴 → 化神 → 大乘 → 飞升，累计阈值自动突破，全程零交互静默运行
- **五项计分**：提问历练 / 任务完成（含文件产出加成）/ Skill 功法（熟练度图鉴）/ 连续活跃道心 / 闭关突破
- **灵力石**：夜间与法定节假日自动掉落，用于解锁**天赋树**（永久增益）
- **随机奖励**：天材地宝 / 功法残卷 / 顿悟等，带条件限制 + 每日上限防刷
- **论道 PK**：异步真实对手 + 五行克制结算（当前因同境对手生态未就绪而暂停，代码保留）
- **防篡改**：`history.jsonl` 行为日志为唯一真相源，校验码粗筛 + PK 日志重放挑战（路线②）
- **洞府主页**：玻璃卡 + 环形进度 + 渐变趋势图 + 功法图鉴 + 灵气粒子，双击即看
- **灵宠卡片**：七大灵宠 × 幼体/成体/巅峰三形态 + 心情系统
- **自动结算**：扫描 WorkBuddy 会话记录按真实使用自动计分，无需手动敲命令

## 📸 预览

> 洞府主页 / 灵宠卡片截图区（可替换为实际截图链接）

## 🚀 快速开始（WorkBuddy 内安装）

### 方式一：git clone（推荐）

```bash
# Windows（PowerShell / CMD）
git clone https://github.com/zhujiaxing0915/workbuddy-xiuxian.git "%USERPROFILE%\.workbuddy\skills\xiuxian"

# macOS / Linux
git clone https://github.com/zhujiaxing0915/workbuddy-xiuxian.git ~/.workbuddy/skills/xiuxian
```

> ⚠️ 目标目录名必须为 `xiuxian`（与 `SKILL.md` 的 `name: xiuxian` 一致，WorkBuddy 按目录名发现技能）。若已存在同名目录，请先备份或删除。

### 方式二：下载 ZIP

1. GitHub 仓库页 → `Code` → `Download ZIP`
2. 解压后把 `workbuddy-xiuxian-main` 目录**重命名为 `xiuxian`**
3. 放到 WorkBuddy 用户级技能目录：`~/.workbuddy/skills/`（Windows 为 `C:\Users\<你>\.workbuddy\skills\`）

### 启用

1. **重启 WorkBuddy**（或刷新技能列表）让其扫描到新技能
2. 聊天框输入 `/xiuxian 初始化 <道号>` 建立修炼身份（例如 `/xiuxian 初始化 青云子`）
3. 输入 `/xiuxian 状态` 查看文字小结并打开洞府主页
4. 可选 · 自动结算：管理员运行 `scripts\install_auto_reconcile.bat` 注册每日 09:00 / 21:00 计划任务，之后无需手动结算

### 命令行验证（不依赖 WorkBuddy UI）

```bash
cd <skill 目录>/scripts
python cli.py init <道号>      # 初始化
python cli.py status           # 查看状态
python cli.py verify           # 自校验
```

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

## 环境要求
- Python 3.10+（**仅标准库，无需 pip 安装**；腾讯在线后端为可选项）。
- 本 skill 零第三方依赖、离线可用；全部数据落在用户级 `~/.workbuddy/xiuxian/`。

## 🐾 右下角宠物浮窗（可选增强）

skill 默认**不修改 WorkBuddy 本体**。若希望 WorkBuddy 右下角出现一只宠物浮窗（透明背景、上下浮动，**点击打开修仙洞府主页**、悬停显示手型），使用仓库自带的通用注入工具：

```bash
cd tools/patch-pet
python patch_pet.py               # 自动定位 WorkBuddy resources/app.asar 并注入（自动备份原文件）
python patch_pet.py --check       # 校验是否已注入
python patch_pet.py --revert      # 从最近的备份恢复原版（回滚）
python patch_pet.py --pet my.png  # 自定义宠物图（推荐透明背景 PNG，128px 显示）
python patch_pet.py --dry-run     # 只预览，不写任何文件
```

- **原理**：纯 Python 解析/重打包 asar（与 @electron/asar 兼容），仅注入两条内容——主 CSS 的浮窗样式 + `index.html` 的点击脚本；**unpacked 树不动**，因此兼容任意 WorkBuddy 版本，且修改前自动备份、`--revert` 一键还原。
- 注入后**重启 WorkBuddy** 生效；若未安装本 skill 的洞府主页，点击浮窗会打开一个不存在的本地文件（可忽略，或先用 `/xiuxian 状态` 生成洞府页）。

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

## License
[MIT](LICENSE) © 2026 zhujiaxing0915
