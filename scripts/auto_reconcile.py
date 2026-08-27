# -*- coding: utf-8 -*-
"""修仙模式 · 自动结算（零交互）

扫描 WorkBuddy 会话记录（~/.workbuddy/projects/*/*.jsonl），按天增量统计
真实使用行为（用户提问 / 对话轮次 / 工具与 Skill 调用 / 文件产出），
自动触发 reconcile.cultivate() 计分，实现"不用手动 /xiuxian 结算"。

设计约束：
- 每天最多结算一次（防刷）；仅处理 cursor 之后新出现的一天
- 幂等：cursor 文件 ~/.workbuddy/xiuxian/auto_cursor.json 记录已结算到的
  最大本地日期与最大事件时间戳
- 首次运行不补历史：从 history.jsonl 最后事件所在日期开始，之后自动
- 用法：
    python auto_reconcile.py --preview   # 只打印将结算内容，不写库
    python auto_reconcile.py --commit    # 真实结算并更新 cursor
    python auto_reconcile.py             # 默认 commit
"""
import os
import sys
import json
import glob
import datetime
import common as C
import reconcile as R

PROJECTS_DIR = os.path.expanduser("~/.workbuddy/projects")
CURSOR_FILE = os.path.join(C.STATE_DIR, "auto_cursor.json")

# 计分档位（对照 thresholds.scoring 的语义）
SIMPLE_MSG_THRESHOLD = 2      # 当天对话轮次 <=2 记简单
COMPLEX_TOOL_THRESHOLD = 3    # 当天工具调用 >=3 视为复杂任务
FILES_CAP = 3                 # 文件产出封顶（对齐 task_file_cap）


def _local_day(ms):
    return datetime.datetime.fromtimestamp(ms / 1000.0).strftime("%Y-%m-%d")


def _load_cursor():
    try:
        with open(CURSOR_FILE, "r", encoding="utf-8-sig") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def _save_cursor(cur):
    with open(CURSOR_FILE, "w", encoding="utf-8") as f:
        json.dump(cur, f, ensure_ascii=False, indent=2)


def _last_history_day():
    """history.jsonl 最后一条事件所在本地日期；无则今天。"""
    evs = C.read_history()
    if evs:
        for ev in reversed(evs):
            if ev.get("day"):
                return ev["day"]
    return C.today_local()


def _skill_name_from_arguments(args):
    if not args:
        return None
    try:
        d = json.loads(args) if isinstance(args, str) else args
    except Exception:
        return None
    if not isinstance(d, dict):
        return None
    for k in ("name", "skill", "skillName", "skill_name"):
        v = d.get(k)
        if isinstance(v, str) and v and not v.startswith("{"):
            return v
    return None


def scan_events(since_ms):
    """遍历会话日志，返回 since_ms 之后的事件列表（保持时间顺序不保证）。"""
    events = []
    for fp in glob.glob(os.path.join(PROJECTS_DIR, "*", "*.jsonl")):
        try:
            with open(fp, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        ev = json.loads(line)
                    except Exception:
                        continue
                    ts = ev.get("timestamp")
                    if not isinstance(ts, (int, float)):
                        continue
                    if ts < since_ms:
                        continue
                    events.append(ev)
        except OSError:
            continue
    return events


def summarize_day(events):
    """按天汇总行为信号。events 为该天事件列表。"""
    user_msgs = 0
    assistant_msgs = 0
    tool_calls = 0
    skill_calls = []
    file_outputs = 0
    for ev in events:
        t = ev.get("type")
        if t == "message":
            if ev.get("role") == "user":
                user_msgs += 1
            elif ev.get("role") == "assistant":
                assistant_msgs += 1
        elif t == "function_call":
            tool_calls += 1
            if ev.get("name") == "Skill":
                sn = _skill_name_from_arguments(ev.get("arguments"))
                if sn:
                    skill_calls.append(sn)
        elif t == "file-history-snapshot":
            tfb = ((ev.get("snapshot") or {}).get("trackedFileBackups")) or {}
            if tfb:
                file_outputs += 1
    turns = user_msgs + assistant_msgs
    complex_task = (user_msgs >= SIMPLE_MSG_THRESHOLD or tool_calls >= COMPLEX_TOOL_THRESHOLD
                    or bool(skill_calls))
    files = min(file_outputs, FILES_CAP) if file_outputs else 0
    skill_name = skill_calls[0] if skill_calls else None
    return {
        "user_msgs": user_msgs, "assistant_msgs": assistant_msgs,
        "turns": turns, "tool_calls": tool_calls, "skill_calls": skill_calls,
        "file_outputs": file_outputs, "complex": complex_task,
        "files": files, "skill_name": skill_name, "active": turns + tool_calls > 0,
    }


def main():
    commit = "--commit" in sys.argv or not ("--preview" in sys.argv)
    preview = "--preview" in sys.argv

    cursor = _load_cursor()
    today = C.today_local()
    if cursor:
        last_day = cursor.get("last_day", _last_history_day())
        last_ts = cursor.get("last_ts", 0)
    else:
        # 首次运行：从 history 最后事件日期开始，不补历史
        last_day = _last_history_day()
        last_ts = 0
        print("[init] 首次运行：从已结算日期 %s 之后开始自动结算（不补历史）" % last_day)

    if last_day >= today:
        print("今日（%s）已结算或无新日期，无需自动结算。last_day=%s" % (today, last_day))
        return

    # 收集 last_ts 之后所有事件
    events = scan_events(last_ts)
    if not events:
        print("无新事件。")
        return

    # 按天分组（只处理 last_day < day <= today）
    by_day = {}
    max_ts = last_ts
    for ev in events:
        ts = ev.get("timestamp") or 0
        if ts > max_ts:
            max_ts = ts
        d = _local_day(ts)
        if last_day < d <= today:
            by_day.setdefault(d, []).append(ev)

    days = sorted(by_day.keys())
    if not days:
        print("没有跨越新日期的事件。")
        return

    print("待结算日期：%s" % days)
    for d in days:
        s = summarize_day(by_day[d])
        if not s["active"]:
            print("  %s：无有效活动，跳过" % d)
            continue
        if preview:
            print("  [preview] %s -> complex=%s files=%s skill=%s "
                  "(turns=%d tools=%d fileouts=%d)" %
                  (d, s["complex"], s["files"], s["skill_name"],
                   s["turns"], s["tool_calls"], s["file_outputs"]))
            continue
        st = R.cultivate(complex_task=s["complex"], files=s["files"],
                         skill_name=s["skill_name"])
        note = "  [commit] %s 结算完成：%s·%s阶 修为 %s" % (d, st["realm"], st["sub"], st["xiuwei"])
        if st.get("_breakthrough"):
            note += " 突破:%s" % st["_breakthrough"]
        print(note)

    if not preview:
        _save_cursor({"last_day": today, "last_ts": max_ts})
        print("cursor 已更新：last_day=%s last_ts=%s" % (today, max_ts))


if __name__ == "__main__":
    main()
