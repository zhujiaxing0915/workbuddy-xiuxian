#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""WorkBuddy 右下角宠物浮窗 · 通用注入工具（纯 Python 标准库，无第三方依赖）

给任意版本的 WorkBuddy 注入右下角宠物浮窗：
  - 读取 resources/app.asar，自动定位主 CSS 与 index.html
  - 注入浮窗 CSS（WORKBUDDY_PET_FLOAT：透明宠物图 + 上下浮动动画）
  - 注入点击脚本（WORKBUDDY_PET_CLICK：点击浮窗打开 ~/.workbuddy/xiuxian/dongfu.html，
    即修仙洞府主页；悬停显示手型光标）
  - 仅重写 app.asar（unpacked 树不动，兼容任何版本、可回滚）

用法：
  python patch_pet.py                 # 打补丁（自动备份原 asar）
  python patch_pet.py --dry-run       # 只检查+预览，不写任何文件
  python patch_pet.py --revert        # 从最近的备份恢复原版
  python patch_pet.py --check         # 校验当前 asar 是否已注入
  python patch_pet.py --asar <path>   # 指定 asar 路径（默认 resources/app.asar）
  python patch_pet.py --pet <png>     # 指定宠物图片（透明 PNG；默认内置灵狐）

原理（asar 格式，与 @electron/asar 兼容）：
  文件 = 8 字节 Pickle 头 + JSON header（Pickle 序列化）+ 数据区。
  header 内每个文件 {size, offset(字符串), integrity?, unpacked?}；unpacked 文件数据
  在磁盘 .unpacked 目录、不在 asar 内。重打包按 header DFS 顺序紧密重排嵌入文件并
  重算 offset，unpacked 标记原样保留 —— 因此只替换 app.asar 即可，unpacked 树无需变动。
"""
import argparse
import base64
import datetime
import glob
import hashlib
import json
import os
import shutil
import struct
import sys

BLOCK_SIZE = 4 * 1024 * 1024  # integrity 块大小（与 @electron/asar 一致）


# ---------------------------------------------------------------------------
# asar 读写
# ---------------------------------------------------------------------------

def _align4(n):
    return (n + 3) & ~3


def read_asar(path):
    """返回 (header_dict, files_tree, data_bytes)。"""
    with open(path, "rb") as f:
        raw = f.read()
    header_len = struct.unpack_from("<I", raw, 4)[0]
    header_buf = raw[8:8 + header_len]
    payload_size = struct.unpack_from("<I", header_buf, 0)[0]
    payload_start = len(header_buf) - payload_size
    str_len = struct.unpack_from("<I", header_buf, payload_start)[0]
    json_bytes = header_buf[payload_start + 4: payload_start + 4 + str_len]
    header = json.loads(json_bytes.decode("utf-8"))
    files = header.get("files", {})
    data = raw[8 + header_len:]
    return header, files, data


def build_asar(header, files_tree, data):
    """按 files_tree DFS 顺序重排数据区并序列化，返回完整 asar 字节。"""
    header["files"] = files_tree
    ordered = []
    _collect_files(files_tree, "", ordered)

    new_data = bytearray()
    offsets = {}
    for entry in ordered:
        if entry["unpacked"]:
            continue
        old = entry["old_offset"]
        new_data += data[old: old + entry["size"]]
        offsets[entry["path"]] = len(new_data) - entry["size"]

    _rewrite_offsets(files_tree, "", offsets)

    json_str = json.dumps(header, ensure_ascii=False, separators=(",", ":"))
    jb = json_str.encode("utf-8")
    payload = struct.pack("<I", len(jb)) + jb
    payload += b"\x00" * (_align4(len(payload)) - len(payload))
    header_buf = struct.pack("<I", len(payload)) + payload
    size_buf = struct.pack("<II", 4, len(header_buf))
    return size_buf + header_buf + bytes(new_data)


def _collect_files(node, prefix, out):
    for name in sorted(node.keys()):
        v = node[name]
        path = prefix + "/" + name if prefix else name
        if "files" in v:
            _collect_files(v["files"], path, out)
        else:
            out.append({
                "path": path,
                "size": int(v["size"]),
                "old_offset": int(v["offset"]) if "offset" in v else None,
                "unpacked": bool(v.get("unpacked")),
            })


def _rewrite_offsets(node, prefix, offsets):
    for name, v in node.items():
        path = prefix + "/" + name if prefix else name
        if "files" in v:
            _rewrite_offsets(v["files"], path, offsets)
        else:
            if v.get("unpacked"):
                v.pop("offset", None)
            elif path in offsets:
                v["offset"] = str(offsets[path])


def integrity_of(data):
    """与 @electron/asar getFileIntegrity 一致。"""
    h = hashlib.sha256(data).hexdigest()
    blocks = []
    for i in range(0, len(data), BLOCK_SIZE):
        blocks.append(hashlib.sha256(data[i:i + BLOCK_SIZE]).hexdigest())
    if not blocks:
        blocks.append(hashlib.sha256(b"").hexdigest())
    return {"algorithm": "SHA256", "hash": h, "blockSize": BLOCK_SIZE, "blocks": blocks}


# ---------------------------------------------------------------------------
# 注入内容
# ---------------------------------------------------------------------------

PET_CSS_MARKER = "WORKBUDDY_PET_FLOAT"
PET_JS_MARKER = "WORKBUDDY_PET_CLICK"


def _load_pet_b64(pet_png):
    if pet_png:
        with open(pet_png, "rb") as f:
            return base64.b64encode(f.read()).decode("ascii")
    here = os.path.dirname(os.path.abspath(__file__))
    cand = os.path.join(here, "assets", "pet_linghu_transparent.png")
    if os.path.exists(cand):
        with open(cand, "rb") as f:
            return base64.b64encode(f.read()).decode("ascii")
    # 兜底 1x1 透明像素（仍可点击打开洞府）
    png = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==")
    return base64.b64encode(png).decode("ascii")


def inject_css(css_text, pet_b64):
    if PET_CSS_MARKER in css_text:
        return css_text  # 幂等
    block = ("\n/* WORKBUDDY_PET_FLOAT */\n"
             "body::after{content:url(data:image/png;base64," + pet_b64 + ");"
             "position:fixed;right:18px;bottom:18px;width:128px;height:128px;"
             "z-index:2147483647;pointer-events:none;"
             "animation:petFloatY 3.2s ease-in-out infinite;"
             "filter:drop-shadow(0 6px 14px rgba(140,90,220,.45));}\n"
             "@keyframes petFloatY{0%,100%{transform:translateY(0)}50%{transform:translateY(-14px)}}\n")
    return css_text + block


def _dongfu_url():
    p = os.path.expanduser("~/.workbuddy/xiuxian/dongfu.html").replace("\\", "/")
    return "file:///" + p


def inject_html(html_text):
    if PET_JS_MARKER in html_text:
        return html_text  # 幂等
    script = (
        "\n  <script>\n"
        "    /* WORKBUDDY_PET_CLICK */\n"
        "    (function () {\n"
        "      var W=128,H=128,R=18,B=18;\n"
        "      var URL='" + _dongfu_url() + "';\n"
        "      function inZone(e){var x0=window.innerWidth-R-W,y0=window.innerHeight-B-H;"
        "return e.clientX>=x0&&e.clientX<=x0+W&&e.clientY>=y0&&e.clientY<=y0+H;}\n"
        "      document.addEventListener('click',function(e){if(inZone(e))window.open(URL,'_blank');},true);\n"
        "      document.addEventListener('mousemove',function(e){document.body.style.cursor=inZone(e)?'pointer':'';},true);\n"
        "      document.addEventListener('mouseleave',function(){document.body.style.cursor='';},true);\n"
        "    })();\n"
        "  </script>\n</head>")
    return html_text.replace("</head>", script, 1)


def find_targets(files_tree):
    """定位主 CSS 与 index.html。返回 (css_path, html_path)。
    主 CSS 优先 index-*.css（index.html 引用的主样式），否则取 renderer/assets 下最长者。"""
    paths = []
    _all_paths(files_tree, "", paths)
    css = None
    html = None
    assets_css = []
    for p in paths:
        if p.endswith(".css") and "assets" in p:
            assets_css.append(p)
        if p.endswith("/renderer/index.html") or p == "renderer/index.html":
            html = p
    idx = [p for p in assets_css if "index-" in os.path.basename(p)]
    if idx:
        css = max(idx, key=len)
    elif assets_css:
        css = max(assets_css, key=len)
    if html is None:
        html = next((p for p in paths if p.endswith("index.html")), None)
    return css, html


def _all_paths(node, prefix, out):
    for name, v in node.items():
        path = prefix + "/" + name if prefix else name
        if "files" in v:
            _all_paths(v["files"], path, out)
        else:
            out.append(path)


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

def _default_asar():
    return os.path.join(os.path.expanduser("~"),
                        "AppData", "Local", "Programs", "WorkBuddy",
                        "resources", "app.asar")


def read_file_at(asar_path, files_tree, data, path):
    parts = path.split("/")
    node = files_tree[parts[0]]          # 顶层：名字 -> 节点
    for part in parts[1:]:               # 子层：节点 -> {"files": {...}}
        node = node["files"][part]
    if node.get("unpacked"):
        with open(os.path.join(os.path.dirname(asar_path) + ".unpacked", path), "rb") as f:
            return f.read()
    off = int(node["offset"])
    size = int(node["size"])
    return bytes(data[off:off + size])


def patch(asar_path, pet_png, dry_run=False):
    if not os.path.exists(asar_path):
        sys.exit("[ERROR] asar not found: %s" % asar_path)
    header, files_tree, data = read_asar(asar_path)
    css_path, html_path = find_targets(files_tree)
    if not css_path or not html_path:
        sys.exit("[ERROR] 未找到主 CSS 或 index.html（%s / %s）" % (css_path, html_path))
    print("[info] css  = %s" % css_path)
    print("[info] html = %s" % html_path)

    pet_b64 = _load_pet_b64(pet_png)
    css_old = read_file_at(asar_path, files_tree, data, css_path).decode("utf-8", "replace")
    html_old = read_file_at(asar_path, files_tree, data, html_path).decode("utf-8", "replace")
    css_new = inject_css(css_old, pet_b64).encode("utf-8")
    html_new = inject_html(html_old).encode("utf-8")

    changed = []
    if css_new != css_old.encode("utf-8"):
        changed.append(("css", css_path, len(css_old.encode("utf-8")), len(css_new)))
    if html_new != html_old.encode("utf-8"):
        changed.append(("html", html_path, len(html_old.encode("utf-8")), len(html_new)))

    if not changed:
        print("[info] asar 已包含浮窗注入（幂等跳过）。")
        return False

    for kind, p, a, b in changed:
        print("[%s] %s : %d -> %d bytes" % (kind, p, a, b))

    if dry_run:
        print("[dry-run] 未写入任何文件。")
        return False

    # 重建数据区：DFS 顺序重排，期间替换 css/html
    ordered = []
    _collect_files(files_tree, "", ordered)
    buf = bytearray()
    new_offsets = {}
    new_sizes = {}
    for entry in ordered:
        if entry["unpacked"]:
            continue
        blob = data[entry["old_offset"]: entry["old_offset"] + entry["size"]]
        if entry["path"] == css_path:
            blob = css_new
        elif entry["path"] == html_path:
            blob = html_new
        new_offsets[entry["path"]] = len(buf)
        new_sizes[entry["path"]] = len(blob)
        buf += blob

    _apply_meta(files_tree, new_offsets, new_sizes,
                {css_path: integrity_of(css_new), html_path: integrity_of(html_new)})

    out = build_asar(header, files_tree, bytes(buf))

    backup = asar_path + ".bak." + datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    shutil.copy2(asar_path, backup)
    tmp = asar_path + ".tmp"
    with open(tmp, "wb") as f:
        f.write(out)
    os.replace(tmp, asar_path)

    print("[ok] 已注入并替换：%s" % asar_path)
    print("[ok] 原文件备份：%s" % backup)
    print("[hint] 重启 WorkBuddy 后右下角出现宠物浮窗，点击打开洞府主页。")
    print("[hint] 回滚：python patch_pet.py --revert")
    return True


def _apply_meta(files_tree, offsets, sizes, integrity):
    _walk_apply(files_tree, "", offsets, sizes, integrity)


def _walk_apply(node, prefix, offsets, sizes, integrity):
    for name, v in node.items():
        path = prefix + "/" + name if prefix else name
        if "files" in v:
            _walk_apply(v["files"], path, offsets, sizes, integrity)
        else:
            if v.get("unpacked"):
                v.pop("offset", None)
            elif path in offsets:
                v["offset"] = str(offsets[path])
            if path in sizes:
                v["size"] = sizes[path]   # size 为数字（offset 为字符串）
            if path in integrity:
                v["integrity"] = integrity[path]


def revert(asar_path):
    baks = sorted(glob.glob(asar_path + ".bak.*"))
    if not baks:
        sys.exit("[ERROR] 没有找到备份文件。")
    bak = baks[-1]
    shutil.copy2(bak, asar_path)
    print("[ok] 已从备份恢复：%s -> %s" % (bak, asar_path))
    print("[hint] 重启 WorkBuddy 生效。")


def check(asar_path):
    if not os.path.exists(asar_path):
        sys.exit("[ERROR] asar not found: %s" % asar_path)
    header, files_tree, data = read_asar(asar_path)
    css_path, html_path = find_targets(files_tree)
    ok = False
    if css_path:
        css = read_file_at(asar_path, files_tree, data, css_path).decode("utf-8", "replace")
        if PET_CSS_MARKER in css:
            print("[check] 浮窗 CSS 已注入：%s" % css_path)
            ok = True
    if html_path:
        html = read_file_at(asar_path, files_tree, data, html_path).decode("utf-8", "replace")
        if PET_JS_MARKER in html:
            print("[check] 点击脚本已注入：%s" % html_path)
            ok = True
    if not ok:
        print("[check] 未检测到浮窗注入（原版 asar）。")
    return ok


def main():
    ap = argparse.ArgumentParser(description="WorkBuddy 宠物浮窗注入工具")
    ap.add_argument("--asar", default=None, help="asar 路径（默认自动定位 WorkBuddy resources/app.asar）")
    ap.add_argument("--pet", default=None, help="自定义宠物 PNG（透明背景）")
    ap.add_argument("--revert", action="store_true", help="从备份恢复")
    ap.add_argument("--check", action="store_true", help="校验是否已注入")
    ap.add_argument("--dry-run", action="store_true", help="只预览不写入")
    args = ap.parse_args()

    asar = os.path.normpath(args.asar) if args.asar else _default_asar()
    if args.revert:
        revert(asar)
    elif args.check:
        check(asar)
    else:
        patch(asar, args.pet, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
