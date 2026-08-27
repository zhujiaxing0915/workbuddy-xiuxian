# -*- coding: utf-8 -*-
"""修仙模式 · 灵宠卡片渲染
读取 state（history.jsonl 重放），生成一张带 CSS 动画的灵宠卡片，
输出到 ~/.workbuddy/xiuxian/pet.html（自包含，图标 base64 内联）。

形态：7 大境界 × 3 小阶 -> 灵狐/灵鹿/火鸾/玉麒麟/青龙/朱雀/神龙。
心情：依据最近一次行为与距上次活跃天数，判定 修炼中/论道胜/论道负/打盹/悠闲。
"""
import os
import re
import base64
import datetime
import common as C

TPL = os.path.join(C.ASSETS_DIR, "pet.html")
OUT = os.path.join(C.STATE_DIR, "pet.html")

# 进化链：大境界 -> (图标 manifest key, 灵宠名)
PET_FORMS = [
    ("练气", "pet_linghu",  "灵狐"),
    ("筑基", "pet_linglu",  "灵鹿"),
    ("金丹", "pet_huoluan", "火鸾"),
    ("元婴", "pet_yuqilin", "玉麒麟"),
    ("化神", "pet_qinglong", "青龙"),
    ("合体", "pet_zhuque",  "朱雀"),
    ("大乘", "pet_shenlong", "神龙"),
    ("飞升", "pet_shenlong", "神龙"),
]

MOODS = {
    "修炼中": {"color": "#7C5CFF", "line": "方才那次修炼，修为又有进益，道心愈明。"},
    "论道胜": {"color": "#F5A623", "line": "论道小胜一场，愈发从容自在。"},
    "论道负": {"color": "#5B7CFA", "line": "方才论道惜败，静心思过，再战不迟。"},
    "打盹":   {"color": "#9AA0B5", "line": "许久未曾修炼，且小憩片刻，养精蓄锐。"},
    "悠闲":   {"color": "#3FB6A8", "line": "今日心境澄明，陪道友在此静坐片刻。"},
}


def _b64_icon(rel_path):
    full = os.path.join(C.SKILL_DIR, rel_path)
    try:
        with open(full, "rb") as f:
            return "data:image/png;base64," + base64.b64encode(f.read()).decode("ascii")
    except Exception:
        return ""


def _pet_form(realm):
    for r, key, name in PET_FORMS:
        if r == realm:
            return key, name
    return "pet_shenlong", "神龙"


# 小阶 -> 图标变体后缀：1 幼体 / 2 成体 / 3 巅峰（巅峰即基础键，无后缀）
_STAGE_SUFFIX = {1: "_you", 2: "_cheng", 3: ""}


def _pet_key(base_key, sub):
    return base_key + _STAGE_SUFFIX.get(sub, "")


def _maturity(sub):
    return {1: "幼体", 2: "成体", 3: "巅峰"}.get(sub, "成体")


def _mood(state):
    events = C.read_history()
    last = events[-1] if events else None
    last_type = last.get("type") if last else None
    last_active = state.get("last_active")
    days_since = None
    if last_active:
        try:
            d = (datetime.date.today()
                 - datetime.datetime.strptime(last_active, "%Y-%m-%d").date()).days
            days_since = d
        except Exception:
            days_since = None
    if last_active is None or (days_since is not None and days_since >= 3):
        return "打盹"
    if last_type == "pk_win":
        return "论道胜"
    if last_type == "pk_loss":
        return "论道负"
    if last_type in ("task", "skill", "daily", "reward"):
        return "修炼中"
    return "悠闲"


def render(state=None, mood_override=None, stage_override=None):
    state = state or C.get_state()
    base_key, pname = _pet_form(state["realm"])
    # 小阶决定变体：预览时可用 stage_override 强制指定
    sub_eff = stage_override if stage_override in (1, 2, 3) else state["sub"]
    key = _pet_key(base_key, sub_eff)
    mood = mood_override or _mood(state)
    m = MOODS.get(mood, MOODS["悠闲"])
    maturity = _maturity(sub_eff)

    bubble = (f"道友{state['daohao']}，我是你的{pname}（{maturity}）。{m['line']}")
    gap = (state["next_threshold"] - state["xiuwei"]) if not state["is_max"] else 0
    next_label = (f"{state['next']['realm']}·{state['next']['sub']}阶"
                  if state.get("next") else "大圆满")

    # 进化阶段指示：当前小阶对应档高亮
    stage_map = {"幼体": "you", "成体": "cheng", "巅峰": "dianfeng"}
    stage_flags = {"you": "", "cheng": "", "dianfeng": ""}
    stage_flags[stage_map.get(maturity, "dianfeng")] = "on"

    repl = {
        "{{DAOHAO}}": state["daohao"],
        "{{PET_ICON_KEY}}": key,
        "{{PET_NAME}}": pname,
        "{{MATURITY}}": maturity,
        "{{REALM_FULL}}": f"{state['realm']} · {state['sub']}阶",
        "{{MOOD_LABEL}}": mood,
        "{{MOOD_COLOR}}": m["color"],
        "{{BUBBLE}}": bubble,
        "{{STAGE_YOU}}": stage_flags["you"],
        "{{STAGE_CHENG}}": stage_flags["cheng"],
        "{{STAGE_DIANFENG}}": stage_flags["dianfeng"],
        "{{PROGRESS_PCT}}": str(state["progress"]),
        "{{XW}}": str(state["xiuwei"]),
        "{{XW_NEXT}}": str(state["next_threshold"]),
        "{{NEXT_REALM_LABEL}}": next_label,
        "{{GAP_NEXT}}": str(gap),
        "{{TOTAL}}": str(state["total"]),
        "{{LINGSHI}}": str(state["lingshi"]),
        "{{STREAK}}": str(state["streak"]),
        "{{WIN}}": str(state["pk"]["win"]),
        "{{LOSE}}": str(state["pk"]["lose"]),
        "{{FOOTER_NOTE}}": "灵宠卡片 · 由修仙模式 Skill 自动生成",
    }
    with open(TPL, "r", encoding="utf-8") as f:
        html = f.read()
    for k, v in repl.items():
        html = html.replace(k, v)
    # 图标内联为 base64（无论出现在 src 还是 JS 字符串中）
    html = re.sub(r'assets/icons/[A-Za-z0-9_/]+\.png',
                  lambda m: _b64_icon(m.group(0)), html)
    os.makedirs(C.STATE_DIR, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(html)
    return OUT


if __name__ == "__main__":
    print("灵宠卡片已生成：", render())
