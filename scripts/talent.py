# -*- coding: utf-8 -*-
"""修仙模式 · 天赋树
消耗灵力石/天赋点解锁节点，效果在 reconcile 计分中生效。
解锁事件写入 history，unlocked_talents 由重放得出（可溯源）。
"""
import common as C


def list_talents():
    state = C.get_state()
    unlocked = set(state.get("unlocked_talents", []))
    out = []
    for t in C.get_talents()["talents"]:
        out.append({
            "id": t["id"], "name": t["name"], "icon": t["icon"],
            "cost": t["cost"], "currency": t["currency"],
            "desc": t["desc"], "unlocked": t["id"] in unlocked,
        })
    return out


def unlock_talent(tid):
    state = C.get_state()
    t = next((x for x in C.get_talents()["talents"] if x["id"] == tid), None)
    if not t:
        return {"ok": False, "msg": f"无此天赋：{tid}"}
    if t["id"] in state.get("unlocked_talents", []):
        return {"ok": False, "msg": "已解锁"}
    cur = state.get(t["currency"], 0)
    if cur < t["cost"]:
        label = "灵力石" if t["currency"] == "lingshi" else "天赋点"
        return {"ok": False, "msg": f"{label}不足（需 {t['cost']}，现有 {cur}）"}
    ts = C.now_utc().isoformat()
    day = C.today_local()
    ev = C.mk("talent", ts, day, talent_id=tid, cost=t["cost"], currency=t["currency"],
              dlingshi=(-t["cost"] if t["currency"] == "lingshi" else 0),
              dtp=(-t["cost"] if t["currency"] == "talent_point" else 0))
    C.append_history(ev)
    st = C.get_state()
    C.save_state(st)
    return {"ok": True, "talent": t, "state": st}


if __name__ == "__main__":
    for t in list_talents():
        print(t["name"], "已解锁" if t["unlocked"] else f"需{t['cost']}{t['currency']}")
