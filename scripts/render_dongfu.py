# -*- coding: utf-8 -*-
"""修仙模式 · 洞府主页渲染
读取 state.json + 论道榜快照，把 dongfu.html 模板渲染为自包含 HTML
（图标内联为 base64，随处可打开），输出到 ~/.workbuddy/xiuxian/dongfu.html
"""
import os
import re
import json
import base64
import datetime
import common as C
import sync_leaderboard as SL

TPL = os.path.join(C.ASSETS_DIR, "dongfu.html")
OUT = os.path.join(C.STATE_DIR, "dongfu.html")

REALM_ICON = {
    "练气": "qi_training", "筑基": "zhuj", "金丹": "jindan", "元婴": "yuanying",
    "化神": "huashen", "大乘": "dacheng", "飞升": "feisheng",
}


def _b64_icon(rel_path):
    full = os.path.join(C.SKILL_DIR, rel_path)
    try:
        with open(full, "rb") as f:
            return "data:image/png;base64," + base64.b64encode(f.read()).decode("ascii")
    except Exception:
        return ""


def _icon_path(icon_key):
    """从 icons_manifest.json 解析图标路径（单一真相源，避免前缀拼错）。"""
    mf = C.get_icons_manifest()
    entry = mf.get(icon_key)
    if entry and entry.get("path"):
        return entry["path"]
    return "assets/icons/" + icon_key + ".png"


def _trend(state):
    events = C.read_history()
    today = datetime.datetime.now().date()
    days = [(today - datetime.timedelta(days=i)).strftime("%Y-%m-%d") for i in range(6, -1, -1)]
    day_dxp = {d: 0 for d in days}
    for e in events:
        d = e.get("day")
        if d in day_dxp:
            day_dxp[d] += (e.get("dxp", 0) or 0)
    window_sum = sum(day_dxp.values())
    offset = state["xiuwei"] - window_sum
    running = offset
    series = []
    for d in days:
        running += day_dxp[d]
        series.append(max(0, running))
    return series


def render(state=None):
    state = state or C.get_state()
    with open(TPL, "r", encoding="utf-8") as f:
        html = f.read()

    gap = (state["next_threshold"] - state["xiuwei"]) if not state["is_max"] else 0
    next_label = (f"{state['next']['realm']}·{state['next']['sub']}阶"
                  if state.get("next") else "大圆满")

    skills_js = []
    for g in C.get_skills_map()["gongfa"]:
        skills_js.append({
            "n": g["name"], "v": state["skills"].get(g["name"], 0),
            "i": _icon_path(g["icon"]),
        })

    # 排名
    allr = SL.read_all()
    ranked = sorted(allr.values(), key=lambda r: int(r.get("总修仙分值", 0) or 0), reverse=True)
    rank_all = next((i for i, r in enumerate(ranked, 1) if r.get("道号") == state["daohao"]),
                    len(ranked) + 1) if ranked else 1
    rank_total = len(ranked)
    rank_same = sum(1 for r in allr.values() if r.get("境界") == state["realm"])

    repl = {
        "{{DAOHAO}}": state["daohao"],
        "{{REALM_FULL}}": f"{state['realm']} · {state['sub']}阶",
        "{{GAP_NEXT}}": str(gap),
        "{{XW}}": str(state["xiuwei"]),
        "{{TOTAL}}": str(state["total"]),
        "{{LINGSHI}}": str(state["lingshi"]),
        "{{STREAK}}": str(state["streak"]),
        "{{PROGRESS_PCT}}": str(state["progress"]),
        "{{XW_CUR}}": str(state["xiuwei"]),
        "{{XW_NEXT}}": str(state["next_threshold"]),
        "{{NEXT_REALM_LABEL}}": next_label,
        "{{RANK_ALL}}": str(rank_all),
        "{{RANK_TOTAL}}": str(rank_total),
        "{{RANK_SAME}}": str(rank_same),
        "{{WIN}}": str(state["pk"]["win"]),
        "{{LOSE}}": str(state["pk"]["lose"]),
        "{{LOOT}}": str(state["pk"]["loot"]),
        "{{AVATAR_ICON_PATH}}": "assets/icons/realm/realm_" + REALM_ICON.get(state["realm"], "qi_training") + ".png",
        "{{SKILLS_JS}}": json.dumps(skills_js, ensure_ascii=False),
        "{{TREND_JS}}": json.dumps(_trend(state), ensure_ascii=False),
        "{{FOOTER_NOTE}}": "洞府主页 · 由修仙模式 Skill 自动生成",
    }
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
    out = render()
    print("洞府主页已生成：", out)
