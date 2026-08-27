# -*- coding: utf-8 -*-
"""修仙模式 · 公共模块
职责：路径解析、配置加载、状态重建（history.jsonl 为唯一真相源）、
境界计算、总修仙分值公式、校验码、日志哈希、Skill 归类、时间工具。
设计原则：所有派生数值均由 rebuild_state() 从 history 重放得出，
state.json 仅作缓存/对外镜像，避免状态漂移。
"""
import os
import json
import hashlib
import random
import datetime

# ---------- 路径 ----------
SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_DIR = os.path.join(SKILL_DIR, "config")
ASSETS_DIR = os.path.join(SKILL_DIR, "assets")
STATE_DIR = os.path.expanduser("~/.workbuddy/xiuxian")
STATE_FILE = os.path.join(STATE_DIR, "state.json")
HISTORY_FILE = os.path.join(STATE_DIR, "history.jsonl")
LEADERBOARD_FILE = os.path.join(STATE_DIR, "leaderboard.json")   # 本地后端
SNAPSHOT_DIR = os.path.join(STATE_DIR, "snapshots")

for _d in (STATE_DIR, SNAPSHOT_DIR):
    try:
        os.makedirs(_d, exist_ok=True)
    except OSError:
        pass

# ---------- 配置加载（带缓存） ----------
_CONFIG_CACHE = {}

def _load_json(name):
    if name in _CONFIG_CACHE:
        return _CONFIG_CACHE[name]
    with open(os.path.join(CONFIG_DIR, name), "r", encoding="utf-8") as f:
        data = json.load(f)
    _CONFIG_CACHE[name] = data
    return data

def get_thresholds(): return _load_json("thresholds.json")
def get_skills_map():  return _load_json("skills_map.json")
def get_talents():     return _load_json("talents.json")
def get_rewards():     return _load_json("rewards.json")
def get_holidays():    return _load_json("holidays.json")
def get_secret():      return _load_json("secret.json")
def get_icons_manifest(): return _load_json("icons_manifest.json")

# ---------- 时间工具 ----------
def now_utc():   return datetime.datetime.now(datetime.timezone.utc)
def now_local(): return datetime.datetime.now()
def date_str(dt): return dt.strftime("%Y-%m-%d")
def today_local(): return date_str(now_local())

def is_night():
    h = now_local().hour
    sc = get_thresholds()["scoring"]
    return sc["night_start"] <= h < sc["night_end"]

def is_holiday(dt=None):
    d = date_str(dt or now_local())
    return d in set(get_holidays().get("holidays", []))

# ---------- 境界计算 ----------
def realm_index(realm, sub):
    levels = get_thresholds()["levels"]
    for i, lv in enumerate(levels):
        if lv["realm"] == realm and lv["sub"] == sub:
            return i
    return -1

def realm_info(xw):
    levels = get_thresholds()["levels"]
    idx = 0
    for i, lv in enumerate(levels):
        if xw >= lv["threshold"]:
            idx = i
    cur = levels[idx]
    nxt = levels[idx + 1] if idx + 1 < len(levels) else None
    cur_th = cur["threshold"]
    nxt_th = nxt["threshold"] if nxt else cur_th
    span = (nxt_th - cur_th) or 1
    prog = 100.0 if not nxt else (xw - cur_th) / span * 100.0
    prog = max(0.0, min(100.0, prog))
    return {
        "index": idx, "realm": cur["realm"], "sub": cur["sub"],
        "cur_threshold": cur_th, "next_threshold": nxt_th,
        "is_max": nxt is None, "progress": round(prog, 1),
        "next": nxt,
    }

def skill_unlocked(state, gname):
    g = next((x for x in get_skills_map()["gongfa"] if x["name"] == gname), None)
    if not g:
        return True
    need = realm_index(g["unlock_realm"], g["unlock_sub"])
    have = realm_index(state.get("realm", "练气"), state.get("sub", 1))
    return have >= need

def main_skill(state):
    skills = state.get("skills", {}) or {}
    if not skills:
        return None
    return max(skills.items(), key=lambda kv: kv[1])[0]

# ---------- 总修仙分值 ----------
def compute_total(xw, lingshi, skills_sum, win, lose, streak, formula=None):
    f = formula or get_thresholds()["formula"]
    S = min(skills_sum, f["s_max"])
    D = min(streak, f["d_max"])
    T = (xw * f["w_weight"]
         + lingshi * f["lingshi_weight"]
         + S * f["skill_w"]
         + win * f["win_w"]
         + lose * f["lose_w"]
         + D * f["streak_w"])
    return int(round(T))

# ---------- 校验码 / 日志哈希 ----------
def compute_checksum(daohao, xw, lingshi, pk_record, total, last_active, update_time, salt=None):
    s = salt or get_secret()["salt"]
    pk = pk_record or {"win": 0, "lose": 0, "loot": 0}
    field_str = "|".join([
        str(daohao), str(xw), str(lingshi),
        f"{pk['win']}-{pk['lose']}-{pk['loot']}",
        str(total), str(last_active), str(update_time),
    ])
    return hashlib.sha256((s + field_str).encode("utf-8")).hexdigest()[:16]

def file_log_hash():
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            data = f.read().encode("utf-8")
    except FileNotFoundError:
        data = b""
    return hashlib.sha256(data).hexdigest()

# ---------- Skill 归类 ----------
def classify_skill(name):
    name_l = (name or "").lower()
    for g in get_skills_map()["gongfa"]:
        for kw in g["keywords"]:
            if kw.lower() in name_l:
                return g["name"]
    return "杂学"

# ---------- 状态存储 ----------
def save_state(state):
    os.makedirs(STATE_DIR, exist_ok=True)
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    os.replace(tmp, STATE_FILE)

def load_state_cache():
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None

def append_history(event):
    os.makedirs(STATE_DIR, exist_ok=True)
    with open(HISTORY_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")

def read_history():
    events = []
    if not os.path.exists(HISTORY_FILE):
        return events
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return events

# ---------- 连续活跃 ----------
def compute_streak(active_days):
    if not active_days:
        return 0
    days = set(active_days)
    today = today_local()
    d = datetime.datetime.strptime(today, "%Y-%m-%d").date()
    if today not in days:
        yest = (d - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
        if yest not in days:
            return 0
        d = datetime.datetime.strptime(yest, "%Y-%m-%d").date()
    streak = 0
    while d.strftime("%Y-%m-%d") in days:
        streak += 1
        d -= datetime.timedelta(days=1)
    return streak

# ---------- 状态重建（唯一真相源） ----------
def rebuild_state():
    events = read_history()
    xw = 0
    lingshi = 0
    talent_points = 0
    skills = {}
    pk = {"win": 0, "lose": 0, "loot": 0}
    active_days = set()
    unlocked = []
    identity = {"daohao": "无名修士", "device_id": "dev_unknown",
                "created_at": now_utc().isoformat()}

    for ev in events:
        t = ev.get("type")
        xw += ev.get("dxp", 0) or 0
        lingshi += ev.get("dlingshi", 0) or 0
        talent_points += ev.get("dtp", 0) or 0
        if t == "init":
            identity["daohao"] = ev.get("daohao", identity["daohao"])
            identity["device_id"] = ev.get("device_id", identity["device_id"])
            identity["created_at"] = ev.get("created_at", identity["created_at"])
        elif t == "skill":
            sn = ev.get("skill")
            if sn:
                skills[sn] = min(skills.get(sn, 0) + (ev.get("dprof", 1) or 1), 10)
        elif t == "pk_win":
            pk["win"] += 1
            pk["loot"] += ev.get("loot", 0) or 0
        elif t == "pk_loss":
            pk["lose"] += 1
        elif t == "talent":
            tid = ev.get("talent_id")
            if tid and tid not in unlocked:
                unlocked.append(tid)
        if ev.get("day"):
            active_days.add(ev["day"])

    # 保证 7 功法齐全（便于图鉴/进度展示）
    for g in get_skills_map()["gongfa"]:
        skills.setdefault(g["name"], 0)

    streak = compute_streak(active_days)
    ri = realm_info(xw)
    total = compute_total(xw, lingshi, sum(skills.values()), pk["win"], pk["lose"], streak)
    update_time = now_utc().isoformat()
    last_active = max(active_days) if active_days else None
    cs = compute_checksum(identity["daohao"], xw, lingshi, pk, total, last_active, update_time)

    return {
        "daohao": identity["daohao"],
        "device_id": identity["device_id"],
        "created_at": identity["created_at"],
        "xiuwei": xw,
        "lingshi": lingshi,
        "talent_points": talent_points,
        "skills": skills,
        "streak": streak,
        "pk": pk,
        "realm": ri["realm"],
        "sub": ri["sub"],
        "progress": ri["progress"],
        "cur_threshold": ri["cur_threshold"],
        "next_threshold": ri["next_threshold"],
        "is_max": ri["is_max"],
        "next": ri["next"],
        "total": total,
        "last_active": last_active,
        "update_time": update_time,
        "checksum": cs,
        "log_hash": file_log_hash(),
        "unlocked_talents": unlocked,
    }

def get_state():
    """始终从 history 重放，返回最新状态。"""
    return rebuild_state()

def refresh():
    st = rebuild_state()
    save_state(st)
    return st

# ---------- 初始化 ----------
def init_state(daohao="无名修士"):
    events = read_history()
    if any(e.get("type") == "init" for e in events):
        return refresh()
    import uuid
    ev = {
        "type": "init",
        "ts": now_utc().isoformat(),
        "day": today_local(),
        "daohao": daohao,
        "device_id": "dev_" + uuid.uuid4().hex[:8],
        "created_at": now_utc().isoformat(),
    }
    append_history(ev)
    return refresh()

# ---------- 小工具 ----------
def mk(type_, ts, day, **kw):
    ev = {"type": type_, "ts": ts, "day": day}
    ev.update(kw)
    return ev

def weighted_choice(items):
    if not items:
        return None
    total = sum(i.get("weight", 1) for i in items)
    r = random.uniform(0, total)
    acc = 0.0
    for i in items:
        acc += i.get("weight", 1)
        if r <= acc:
            return i
    return items[-1]

def reward_amount(r):
    a = r.get("amount", 1)
    if isinstance(a, list) and len(a) == 2:
        return random.randint(a[0], a[1])
    return a

def count_events_today(types):
    today = today_local()
    return sum(1 for e in read_history() if e.get("day") == today and e.get("type") in types)

def count_complex_today():
    today = today_local()
    return sum(1 for e in read_history() if e.get("day") == today and e.get("complex"))

if __name__ == "__main__":
    print(json.dumps(get_state(), ensure_ascii=False, indent=2))
