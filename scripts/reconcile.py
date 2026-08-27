# -*- coding: utf-8 -*-
"""修仙模式 · 对账计分引擎
入口：
  cultivate(complex_task, files, skill_name, desc)  -> 记录一次修炼会话并结算
  reconcile()                                       -> 仅刷新状态缓存（供自动化调用）
设计：cultivate 仅向 history 追加事件，派生数值全部由 common.rebuild_state 重放得出。
"""
import random
import common as C


def _roll_rewards(events, ts, day, state, first_skill):
    """按条件与权重抽取随机奖励（每日上限受 common 配置约束）。"""
    cap = C.get_thresholds()["random_reward_daily_cap"]
    eligible = []
    for r in C.get_rewards()["rewards"]:
        if _cond_true(r, state, first_skill):
            eligible.append(r)
    picks = 0
    while picks < cap and eligible:
        r = C.weighted_choice(eligible)
        amt = C.reward_amount(r)
        ev = C.mk("reward", ts, day, reward=r["id"], complex=False)
        if r["type"] == "lingshi":
            ev["dlingshi"] = amt
        elif r["type"] == "xiuwei":
            ev["dxp"] = amt
        elif r["type"] == "talent_point":
            ev["dtp"] = amt
        elif r["type"] == "prof_boost":
            target = state.get("main_skill_tmp") or C.main_skill(state) or "杂学"
            ev["dprof"] = amt
            ev["skill"] = target
        events.append(ev)
        eligible.remove(r)
        picks += 1
    return picks


def _cond_true(r, state, first_skill):
    c = r["condition"]
    if c == "streak>=3":
        return (state.get("streak", 0) or 0) >= 3
    if c == "complex_today>=2":
        return C.count_complex_today() + 1 >= 2
    if c == "night_or_holiday":
        return C.is_night() or C.is_holiday()
    if c == "new_skill_first":
        return bool(first_skill)
    return False


def cultivate(complex_task=False, files=0, skill_name=None, desc=""):
    """记录一次修炼会话。返回最新状态 dict。"""
    ts = C.now_utc().isoformat()
    day = C.today_local()
    th = C.get_thresholds()
    sc = th["scoring"]
    state = C.get_state()

    events = []

    # 1) 提问 + 任务完成基础分
    q = sc["question_complex"] if complex_task else sc["question_simple"]
    t_base = sc["task_base"]
    t_files = min(int(files), sc["task_file_cap"]) * sc["task_file"]
    closedoor = sc["task_closedoor"] if complex_task else 0
    dxp = q + t_base + t_files + closedoor
    events.append(C.mk("task", ts, day, dxp=dxp, complex=bool(complex_task), files=int(files)))

    # 2) 功法修炼
    first_skill = False
    if skill_name:
        gname = C.classify_skill(skill_name)
        state["main_skill_tmp"] = gname
        skill_dxp = sc["skill_use"]
        unlocked = C.skill_unlocked(state, gname)
        # 天赋：灵脉根（修为 +8%）
        if "talent_root" in state.get("unlocked_talents", []):
            skill_dxp = int(round(skill_dxp * 1.08))
        # 天赋：专精（主修功法 +15%）
        if ("talent_xibie" in state.get("unlocked_talents", []) and
                C.main_skill(state) == gname):
            skill_dxp = int(round(skill_dxp * 1.15))
        first_skill = (state.get("skills", {}).get(gname, 0) == 0)
        prof_gain = 2 if "talent_shuli" in state.get("unlocked_talents", []) else 1
        events.append(C.mk("skill", ts, day, dxp=skill_dxp, skill=gname,
                           dprof=prof_gain, first_skill=first_skill,
                           locked=(not unlocked)))

    # 3) 灵力石掉落（夜间/节假日）
    if C.is_night() or C.is_holiday():
        smin, smax = sc["stone_session_min"], sc["stone_session_max"]
        drop = random.randint(smin, smax)
        if C.is_holiday():
            drop += sc["stone_holiday_bonus"]
        events.append(C.mk("daily", ts, day, dlingshi=drop, kind="stone"))

    # 4) 随机奖励（带条件 + 每日上限）
    _roll_rewards(events, ts, day, state, first_skill)

    # 写入所有事件
    for ev in events:
        C.append_history(ev)

    # 5) 突破检测 -> 顿悟奖励（不受随机奖励上限约束）
    before_xw = state["xiuwei"]
    after = C.get_state()
    broke = (after["realm"] != state["realm"]) or (after["sub"] != state["sub"])
    if broke:
        bt = []
        amt = random.randint(*_reward_range("dunwu"))
        bt.append(C.mk("reward", ts, day, dxp=amt, reward="dunwu", breakthrough=True))
        if "talent_xiuwei" in after.get("unlocked_talents", []):
            gap = after["cur_threshold"] - before_xw
            if gap > 0:
                bt.append(C.mk("reward", ts, day, dxp=int(round(gap * 0.15)),
                               reward="breakthrough_crit"))
        for ev in bt:
            C.append_history(ev)
        after = C.get_state()
        after["_breakthrough"] = {"from": f"{state['realm']}·{state['sub']}阶",
                                  "to": f"{after['realm']}·{after['sub']}阶"}
    state.pop("main_skill_tmp", None)
    after.pop("main_skill_tmp", None)
    C.save_state(after)
    return after


def _reward_range(rid):
    for r in C.get_rewards()["rewards"]:
        if r["id"] == rid:
            a = r.get("amount", [20, 50])
            return tuple(a) if isinstance(a, list) else (a, a)
    return (20, 50)


def reconcile():
    """自动化对账：仅刷新缓存（实际计分由 cultivate 显式触发）。"""
    return C.refresh()


if __name__ == "__main__":
    import sys
    args = sys.argv[1:]
    complex_task = "--complex" in args
    files = 0
    if "--files" in args:
        i = args.index("--files")
        try:
            files = int(args[i + 1])
        except (IndexError, ValueError):
            files = 0
    skill = None
    if "--skill" in args:
        i = args.index("--skill")
        try:
            skill = args[i + 1]
        except IndexError:
            skill = None
    st = cultivate(complex_task=complex_task, files=files, skill_name=skill)
    print(f"道号 {st['daohao']} | 境界 {st['realm']}·{st['sub']}阶 | "
          f"修为 {st['xiuwei']} | 灵力石 {st['lingshi']} | 连续 {st['streak']} 天")
    if st.get("_breakthrough"):
        print("突破：", st["_breakthrough"])
