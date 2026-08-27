# -*- coding: utf-8 -*-
"""修仙模式 · 论道 PK 引擎
- 解锁：练气二层（小阶 2）
- 匹配：仅同大境界（±1 容差）真实对手；无对手时降级或引导本地演武
- 校验：候选对手需通过公式+签名双重复核，否则标"道行存疑"不入池
- 结算：属性差 + 五行克制 + 随机波动 -> 胜负与掠宝
- 写入：战报表只追加；胜方本地即时入账，败方由被告异步兑现（本地实现仅更新自身）
"""
import os
import json
import random
import datetime
import common as C
import sync_leaderboard as SL


def _unlocked(state):
    need = C.realm_index(
        C.get_thresholds()["pk"]["unlock_realm"],
        C.get_thresholds()["pk"]["unlock_sub"])
    have = C.realm_index(state["realm"], state["sub"])
    return have >= need


def _element_multiplier(att_main, def_main):
    fe = C.get_thresholds()["pk"]["five_element"]
    if fe.get(att_main) == def_main:
        return 1.15
    if fe.get(def_main) == att_main:
        return 0.85
    return 1.0


def _sigmoid(x):
    import math
    try:
        return 1.0 / (1.0 + math.exp(-x))
    except OverflowError:
        return 0.0 if x < 0 else 1.0


def _virtual_opponent(state):
    """本地演武：规则生成的历史最佳镜像对手。"""
    name = random.choice(["玄机子", "青冥", "赤霄", "白鹿", "墨渊", "凌霄"])
    base = max(state["xiuwei"], 50)
    xw = int(base * random.uniform(0.7, 1.3))
    ri = C.realm_info(xw)
    lingshi = random.randint(0, 20)
    gongfa = random.choice(C.get_skills_map()["gongfa"])["name"]
    return {
        "道号": f"[演武]{name}", "境界": ri["realm"], "小阶": ri["sub"],
        "修为": xw, "主修功法": gongfa, "灵力石": lingshi,
        "战绩": f"{random.randint(0,5)}胜{random.randint(0,5)}负",
        "总修仙分值": xw, "校验码": "local", "virtual": True,
    }


def _resolve(attacker, defender):
    aT = attacker["total"]
    dT = int(defender.get("总修仙分值", defender.get("修为", 0)) or 0)
    diff = aT - dT
    p = _sigmoid(diff / 3000.0)
    att_main = C.main_skill(attacker) or "杂学"
    def_main = defender.get("主修功法", "杂学")
    em = _element_multiplier(att_main, def_main)
    p = max(0.1, min(0.9, p * em))
    win = random.random() < p
    loot = 0
    if win:
        pk = C.get_thresholds()["pk"]
        loot = min(int(defender.get("灵力石", 0) or 0),
                   random.randint(pk["loot_min"], pk["loot_max"]))
    return win, round(p, 3), em, loot


def _report(attacker, defender, win, p, em, loot, virtual):
    att_main = C.main_skill(attacker) or "杂学"
    def_main = defender.get("主修功法", "杂学")
    lines = []
    lines.append("═══════ 论 道 战 报 ══════")
    lines.append(f" challenger：{attacker['daohao']}（{attacker['realm']}·{attacker['sub']}阶 / 主修 {att_main}）")
    lines.append(f" 守方　　：{defender['道号']}（{defender['境界']}·{defender.get('小阶',1)}阶 / 主修 {def_main}）")
    if virtual:
        lines.append(" 〔本地演武 · 非真人对手〕")
    lines.append("────────────────────────")
    ele_txt = "克制" if em > 1 else ("被克" if em < 1 else "相生")
    lines.append(f" 功法克制：{ele_txt}（系数 {em}）　胜率估算 {int(p*100)}%")
    rounds = random.randint(3, 5)
    for i in range(1, rounds + 1):
        a = random.randint(20, 120)
        d = random.randint(20, 120)
        if a >= d:
            lines.append(f" 第{i}回合：{attacker['daohao']} 御 {a} 道韵，破 {defender['道号']} {d} 守势 ✦")
        else:
            lines.append(f" 第{i}回合：{defender['道号']} 御 {d} 道韵，挡 {attacker['daohao']} {a} 攻势 ✧")
    lines.append("────────────────────────")
    if win:
        lines.append(f" 战果：★ {attacker['daohao']} 胜！掠得灵力石 {loot} 枚")
    else:
        lines.append(f" 战果：☆ {attacker['daohao']} 惜败，道心未损（待守方异步兑现）")
    lines.append("════════════════════════")
    return "\n".join(lines)


def run_pk(state=None, opponent_name=None, force_virtual=False):
    state = state or C.get_state()
    if not _unlocked(state):
        return {"ok": False, "msg": "道行尚浅，练气二层方可论道。"}

    virtual = False
    defender = None
    suspicious = []

    if force_virtual:
        defender = _virtual_opponent(state)
        virtual = True
    else:
        # 候选对手
        candidates = SL.get_candidates(state["realm"], state["sub"],
                                       tol=1, exclude_daohao=state["daohao"])
        suspicious = []
        valid = []
        for c in candidates:
            verdict, why = SL.verify_row(c)
            if verdict == "ok":
                valid.append(c)
            else:
                suspicious.append((c.get("道号", "?"), why))

        if opponent_name:
            defender = next((c for c in valid if c.get("道号") == opponent_name), None)
            if not defender:
                return {"ok": False, "msg": f"未找到同境对手「{opponent_name}」"}
        elif valid:
            defender = random.choice(valid)
        elif candidates:
            # 有候选但全部存疑 -> 不入池
            return {"ok": False,
                    "msg": "同境对手道行存疑（校验未过），不入论道。",
                    "suspicious": suspicious}
        else:
            defender = _virtual_opponent(state)
            virtual = True

    win, p, em, loot = _resolve(state, defender)
    report = _report(state, defender, win, p, em, loot, virtual)

    # 写入战报表（只追加）
    record = {
        "记录ID": "PK" + datetime.datetime.utcnow().strftime("%Y%m%d%H%M%S"),
        "挑战者道号": state["daohao"],
        "守方道号": defender["道号"],
        "结果": "胜" if win else "负",
        "挑战者战前修为": state["xiuwei"],
        "守方战前修为": defender.get("修为", 0),
        "掠取灵力石": loot if win else 0,
        "签名": state["checksum"],
        "状态": "pending",
        "时间戳": C.now_utc().isoformat(),
    }
    SL.append_battle(record)

    # 更新本地状态
    if win:
        C.append_history(C.mk("pk_win", C.now_utc().isoformat(), C.today_local(),
                              loot=loot, defender=defender["道号"]))
    else:
        C.append_history(C.mk("pk_loss", C.now_utc().isoformat(), C.today_local(),
                              defender=defender["道号"]))
    st = C.get_state()
    C.save_state(st)

    return {
        "ok": True, "win": win, "report": report, "loot": loot,
        "virtual": virtual, "suspicious": suspicious, "state": st,
    }


if __name__ == "__main__":
    st = C.init_state("测试修士")
    # 给一点修为以便解锁
    for _ in range(3):
        C.append_history(C.mk("task", C.now_utc().isoformat(), C.today_local(), dxp=40))
    st = C.get_state()
    res = run_pk(st)
    print(res.get("report", res.get("msg")))
