# -*- coding: utf-8 -*-
"""修仙模式 · 命令行入口
支持子命令（中英文均可）：
  init [道号]        初始化修炼身份
  status / 状态       文字小结并渲染洞府主页
  cultivate / 结算 [--complex] [--files N] [--skill NAME]   记录一次修炼会话
  pk / 论道 [对手]    触发一次论道（文字战报）
  talent / 天赋 [--list | --unlock ID]   天赋树
  render / 洞府       仅重渲染洞府主页
  sync / 同步         同步论道榜主表
  snapshot / 快照     每日快照
  verify / 校验       自校验（状态 vs 重放一致性）
  pet / 宠物 [--mood 修炼中|论道胜|论道负|打盹|悠闲] [--stage you|cheng|dianfeng]   生成灵宠卡片
"""
import sys
import os
import json
import common as C
import reconcile as R
import talent as T
import pk_engine as PK
import sync_leaderboard as SL
import render_dongfu as RD
import render_pet as RP

ALIAS = {
    "init": "init", "初始化": "init",
    "status": "status", "状态": "status",
    "cultivate": "cultivate", "结算": "cultivate",
    "pk": "pk", "论道": "pk",
    "talent": "talent", "天赋": "talent",
    "render": "render", "洞府": "render",
    "sync": "sync", "同步": "sync",
    "snapshot": "snapshot", "快照": "snapshot",
    "verify": "verify", "校验": "verify",
    "pet": "pet", "宠物": "pet",
}


def _ensure_init(daohao=None):
    if not os.path.exists(C.HISTORY_FILE):
        C.init_state(daohao or "无名修士")
    return C.get_state()


def _flag(args, name):
    return name in args


def _kv(args, name, default=None):
    if name in args:
        i = args.index(name)
        if i + 1 < len(args):
            return args[i + 1]
    return default


def _summary(st):
    return (f"道号：{st['daohao']}　境界：{st['realm']}·{st['sub']}阶\n"
            f"修为：{st['xiuwei']}　总修仙分：{st['total']}\n"
            f"灵力石：{st['lingshi']}　天赋点：{st.get('talent_points',0)}\n"
            f"连续活跃：{st['streak']} 天　功法：{st['skills']}\n"
            f"论道：{st['pk']['win']}胜 {st['pk']['lose']}负　掠宝 {st['pk']['loot']} 枚\n"
            f"校验码：{st['checksum']}")


def cmd_init(args):
    dh = _kv(args, "--daohao")
    if dh is None:
        # 位置参数：子命令（args[0]）之后第一个非旗标参数即道号
        pos = [a for a in args[1:] if not a.startswith("-")]
        dh = pos[0] if pos else "无名修士"
    st = C.init_state(dh)
    print("初始化完成：", _summary(st))


def cmd_status(args):
    st = _ensure_init()
    print(_summary(st))
    out = RD.render(st)
    print("洞府主页：", out)


def cmd_cultivate(args):
    st = _ensure_init()
    complex_task = _flag(args, "--complex")
    files = int(_kv(args, "--files", 0) or 0)
    skill = _kv(args, "--skill")
    desc = _kv(args, "--desc", "")
    st = R.cultivate(complex_task=complex_task, files=files, skill_name=skill, desc=desc)
    print(f"修炼结算：{st['daohao']} | {st['realm']}·{st['sub']}阶 | 修为 {st['xiuwei']} | 灵力石 {st['lingshi']}")
    if st.get("_breakthrough"):
        print("突破：", st["_breakthrough"])
    out = RD.render(st)
    print("洞府主页：", out)


def cmd_pk(args):
    st = _ensure_init()
    print("论道 PK 暂时关闭：当前论道条件不满足（同境真实对手生态未就绪）。"
          "请先专注修行（/xiuxian 结算），开放时间另行通知。")
    return


def cmd_talent(args):
    if _flag(args, "--list") or len(args) <= 2:
        for t in T.list_talents():
            mark = "✔" if t["unlocked"] else f"需{t['cost']}{t['currency']}"
            print(f"{t['name']}（{t['id']}）：{t['desc']}  [{mark}]")
        return
    if _flag(args, "--unlock"):
        tid = _kv(args, "--unlock")
        r = T.unlock_talent(tid)
        print(r.get("msg") or f"已解锁：{r.get('talent', {}).get('name')}")
        if r.get("ok"):
            st = r["state"]
            print(f"剩余灵力石：{st['lingshi']}　剩余天赋点：{st.get('talent_points',0)}")


def cmd_render(args):
    st = _ensure_init()
    out = RD.render(st)
    print("洞府主页已渲染：", out)


def cmd_sync(args):
    st = _ensure_init()
    r = SL.upsert(st)
    print("同步结果：", r)
    print("候选同境对手数：", len(SL.get_candidates(st["realm"], st["sub"])))


def cmd_snapshot(args):
    print("快照：", SL.snapshot())


def cmd_pet(args):
    st = _ensure_init()
    mood = _kv(args, "--mood")
    stage = _kv(args, "--stage")
    stage_map = {"you": 1, "幼体": 1, "cheng": 2, "成体": 2,
                 "dianfeng": 3, "巅峰": 3, "peak": 3}
    stage_override = stage_map.get((stage or "").lower()) if stage else None
    out = RP.render(st, mood_override=mood, stage_override=stage_override)
    print("灵宠卡片：", out)


def cmd_verify(args):
    st = _ensure_init()
    # 1) 校验码自洽：用状态自身字段（含自身 update_time）重算，应与存储值一致
    cs = C.compute_checksum(st["daohao"], st["xiuwei"], st["lingshi"], st["pk"],
                            st["total"], st["last_active"], st["update_time"])
    ok_cs = (cs == st["checksum"])
    # 2) 重放确定性：再重放一次，比较派生数值（不含会漂移的时间字段）
    r2 = C.rebuild_state()
    ok_replay = (r2["xiuwei"] == st["xiuwei"] and r2["total"] == st["total"]
                 and r2["pk"] == st["pk"] and r2["skills"] == st["skills"]
                 and r2["lingshi"] == st["lingshi"] and r2["streak"] == st["streak"])
    print(f"校验码自洽：{'通过' if ok_cs else '失败'}")
    print(f"重放一致性：{'通过' if ok_replay else '失败'}")
    print("结论：", "状态健康" if (ok_cs and ok_replay) else "检测到不一致，建议重新 cultivate 或检查 history")


def main():
    args = sys.argv[1:]
    cmd = ALIAS.get(args[0], "status") if args else "status"
    {
        "init": cmd_init,
        "status": cmd_status,
        "cultivate": cmd_cultivate,
        "pk": cmd_pk,
        "talent": cmd_talent,
        "render": cmd_render,
        "sync": cmd_sync,
        "snapshot": cmd_snapshot,
        "verify": cmd_verify,
        "pet": cmd_pet,
    }[cmd](args)


if __name__ == "__main__":
    main()
