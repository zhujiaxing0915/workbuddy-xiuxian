# -*- coding: utf-8 -*-
"""修仙模式 · 论道榜同步（双表结构）
- 主表：各修士实时行（道号为唯一键，有则更新无则新增）
- 战报表：对战结果只追加（pending -> resolved）
默认使用本地后端（~/.workbuddy/xiuxian/leaderboard.json + battles.jsonl），
完全可离线运行与测试；设置环境变量 XIUXIAN_TENCENT=1 且腾讯文档 CLI 可用时切换为在线后端。
"""
import os
import json
import subprocess
import common as C

# 主表字段顺序（含防篡改列）
FIELDS = ["道号", "境界", "小阶", "修为", "主修功法", "灵力石", "战绩",
          "最近活跃", "更新时间", "总修仙分值", "校验码", "日志哈希"]

TD_FILE_ID = "WhliUmAAkOJL"   # 修仙论道榜
TD_SHEET_ID = "BB08J2"
TD_BATTLE_FILE_ID = "WjaLwseDyatk"  # 修仙论道战报表

BATTLES_LOCAL = os.path.join(C.STATE_DIR, "battles.jsonl")


# ---------------- 行构造 ----------------
def row_from_state(st):
    pk = st.get("pk", {}) or {}
    record = f"{pk.get('win', 0)}胜{pk.get('lose', 0)}负"
    return {
        "道号": st["daohao"],
        "境界": st["realm"],
        "小阶": st["sub"],
        "修为": st["xiuwei"],
        "主修功法": C.main_skill(st) or "杂学",
        "灵力石": st["lingshi"],
        "战绩": record,
        "最近活跃": st["last_active"],
        "更新时间": st["update_time"],
        "总修仙分值": st["total"],
        "校验码": st["checksum"],
        "日志哈希": st.get("log_hash", ""),
    }


# ---------------- 在线后端（默认关闭） ----------------
def _td_cli():
    """返回腾讯文档 CLI 绝对路径；不可用返回 None。"""
    if os.environ.get("XIUXIAN_TENCENT") != "1":
        return None
    cand = (r"C:\Users\Administrator\.workbuddy\plugins\cache\workbuddy-builtin"
            r"\tencent-docs-plugin\1.0.0\skills\tencent-docs\tencentdocs.py")
    return cand if os.path.exists(cand) else None


def _td_call(cli, tool, payload):
    out = subprocess.run(
        ["python", cli, "tdoc_call", "sheet-mcp", tool, json.dumps(payload)],
        capture_output=True, text=True, timeout=30)
    if out.returncode != 0:
        raise RuntimeError(out.stderr.strip() or "tdoc_call failed")
    return json.loads(out.stdout)


def _tencent_read_all():
    cli = _td_cli()
    if not cli:
        raise RuntimeError("online backend disabled")
    data = _td_call(cli, "get_range_value",
                    {"file_id": TD_FILE_ID, "sheet_id": TD_SHEET_ID,
                     "start_row": 1, "start_col": 0, "end_row": 1000, "end_col": len(FIELDS) - 1})
    rows = data.get("values", [])
    result = {}
    for r in rows:
        if not r or not r[0]:
            continue
        obj = {FIELDS[i]: (r[i] if i < len(r) else "") for i in range(len(FIELDS))}
        result[obj["道号"]] = obj
    return result


def _tencent_upsert(st):
    cli = _td_cli()
    if not cli:
        raise RuntimeError("online backend disabled")
    allr = _tencent_read_all()
    row = row_from_state(st)
    # 找到道号所在行（从 2 开始，1 为表头）
    target = None
    idx = 2
    for name in allr:
        if name == st["daohao"]:
            target = idx
            break
        idx += 1
    if target is None:
        target = idx  # 追加新行
    _td_call(cli, "set_range_value_by_csv", {
        "file_id": TD_FILE_ID, "sheet_id": TD_SHEET_ID,
        "start_row": target - 1, "start_col": 0,
        "csv_data": ",".join(str(row[f]) for f in FIELDS)})
    return {"backend": "tencent"}


def _tencent_append_battle(record):
    cli = _td_cli()
    if not cli:
        raise RuntimeError("online backend disabled")
    _td_call(cli, "set_range_value_by_csv", {
        "file_id": TD_BATTLE_FILE_ID, "sheet_id": TD_SHEET_ID,
        "start_row": 0, "start_col": 0,
        "csv_data": ",".join(str(record.get(f, "")) for f in
            ["记录ID", "挑战者道号", "守方道号", "结果", "挑战者战前修为",
             "守方战前修为", "掠取灵力石", "签名", "状态", "时间戳"])})
    return {"backend": "tencent"}


# ---------------- 本地后端（默认，完整可用） ----------------
def _load_local():
    try:
        with open(C.LEADERBOARD_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_local(lb):
    os.makedirs(C.STATE_DIR, exist_ok=True)
    tmp = C.LEADERBOARD_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(lb, f, ensure_ascii=False, indent=2)
    os.replace(tmp, C.LEADERBOARD_FILE)


def _local_upsert(st, note=""):
    lb = _load_local()
    lb[st["daohao"]] = row_from_state(st)
    _save_local(lb)
    return {"backend": "local", "note": note}


def _local_append_battle(record):
    os.makedirs(C.STATE_DIR, exist_ok=True)
    with open(BATTLES_LOCAL, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return {"backend": "local"}


# ---------------- 对外接口 ----------------
def upsert(st):
    try:
        return _tencent_upsert(st)
    except Exception as e:  # 在线失败 -> 回退本地，绝不阻塞本地逻辑
        return _local_upsert(st, note=str(e))


def read_all():
    try:
        return _tencent_read_all()
    except Exception:
        return _load_local()


def get_candidates(realm, sub, tol=1, exclude_daohao=None):
    allr = read_all()
    myidx = C.realm_index(realm, sub)
    out = []
    for name, row in allr.items():
        if exclude_daohao and name == exclude_daohao:
            continue
        ridx = C.realm_index(row.get("境界", "练气"), int(row.get("小阶", 1) or 1))
        if abs(ridx - myidx) <= tol:
            out.append(row)
    return out


def verify_row(row):
    """公式 + 签名双重校验，返回 ('ok'|'data'|'sign', 说明)。"""
    try:
        w = int(row.get("修为", 0) or 0)
        l = int(row.get("灵力石", 0) or 0)
        win, lose = _parse_record(row.get("战绩", "0胜0负"))
        total = int(row.get("总修仙分值", 0) or 0)
        streak_days = 0  # 远程不持有连续天数，跳过 D 项（仅本地重放才算）
        skills_sum = 0
        T = C.compute_total(w, l, skills_sum, win, lose, streak_days)
        if T != total:
            return ("data", f"总修仙分值不符(重算{T}≠表{total})")
        cs = C.compute_checksum(row.get("道号", ""), w, l,
                                {"win": win, "lose": lose, "loot": 0},
                                total, row.get("最近活跃"), row.get("更新时间"))
        if cs != row.get("校验码"):
            return ("sign", "校验码不符")
        return ("ok", "通过")
    except Exception as e:
        return ("data", f"校验异常:{e}")


def _parse_record(s):
    import re
    m = re.search(r"(\d+)\s*胜\s*(\d+)\s*负", str(s))
    if m:
        return int(m.group(1)), int(m.group(2))
    return 0, 0


def append_battle(record):
    try:
        return _tencent_append_battle(record)
    except Exception:
        return _local_append_battle(record)


def snapshot():
    """每日 UTC 0:00 快照（自愈用）。"""
    import datetime
    os.makedirs(C.SNAPSHOT_DIR, exist_ok=True)
    stamp = datetime.datetime.utcnow().strftime("%Y%m%d")
    path = os.path.join(C.SNAPSHOT_DIR, f"论道榜_{stamp}.json")
    try:
        data = read_all()
    except Exception:
        data = {}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return path


if __name__ == "__main__":
    st = C.get_state()
    print("upsert ->", upsert(st))
    print("candidates(练气) ->", len(get_candidates(st["realm"], st["sub"])))
