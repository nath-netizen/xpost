#!/usr/bin/env python3
"""memdash — a live, local memory dashboard (Activity Monitor, but more detailed).

Run it on the machine you want to inspect:

    python3 tools/memdash/memdash.py            # opens http://127.0.0.1:8765
    python3 tools/memdash/memdash.py --port 9000 --no-open

Standard library only (Python 3.8+). macOS is the primary target and uses the
same kernel counters Activity Monitor reads (vm_stat, sysctl, top). Linux is
supported through /proc for testing and for Linux boxes.

The server binds to 127.0.0.1 only. The one state-changing endpoint (/api/quit,
a graceful "quit app" via AppleScript) requires a per-run token that is only
embedded in the page this server serves, and it only accepts apps that appeared
in the latest sample.
"""

import argparse
import json
import os
import platform
import re
import secrets
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
GB = 1024 ** 3
MB = 1024 ** 2

SYS_INTERVAL = 2.0     # seconds between system-counter samples
PROC_INTERVAL = 5.0    # seconds between process samples (top is slow on macOS)
HISTORY_LEN = 900      # 30 minutes at 2 s


def run(cmd, timeout=10):
    try:
        out = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                             timeout=timeout, check=False)
        return out.stdout.decode("utf-8", "replace")
    except (OSError, subprocess.SubprocessError):
        return ""


# --------------------------------------------------------------------------
# App classification
# --------------------------------------------------------------------------

BROWSERS = {
    "Google Chrome": "Chrome: Settings → Performance → Memory Saver → Maximum; chrome://discards to drop tabs now.",
    "Google Chrome Canary": "Chrome: Settings → Performance → Memory Saver → Maximum.",
    "Chromium": "Settings → Performance → Memory Saver.",
    "Microsoft Edge": "Edge: Settings → System and performance → Sleeping tabs → 30 s.",
    "Brave Browser": "Brave: Settings → System → Memory Saver.",
    "Arc": "Arc: lower Auto-Archive to 12 h; archived tabs release memory.",
    "Dia": "Close tab groups you are not using.",
    "Comet": "Close tab groups you are not using.",
    "Vivaldi": "Vivaldi: right-click tab stack → Hibernate background tabs.",
    "Opera": "Opera: Settings → Tab snoozing.",
    "Firefox": "Firefox: about:unloads → Unload the heaviest tabs; set browser.tabs.unloadOnLowMemory.",
    "Safari": "Safari: close tabs/windows; pinned and audio tabs never get suspended.",
    "ChatGPT Atlas": "Close tabs you are not using.",
}
VM_RE = re.compile(r"\b(docker|orbstack|virtual machine service|qemu[\w-]*|utm|parallels[\w ]*|vmware[\w ]*|"
                   r"colima|limactl|podman|virtualbox|vboxheadless|multipass)\b", re.I)
LLM_RE = re.compile(r"^(ollama|lm studio|lmstudio|llama-server|llama\.cpp|mlx_lm|msty)", re.I)
SYSTEM_NAMES = {"kernel_task", "WindowServer", "launchd", "loginwindow", "Finder", "Dock",
                "SystemUIServer", "mds", "mds_stores", "mdworker", "mdworker_shared",
                "photoanalysisd", "mediaanalysisd", "spotlightknowledged", "systemd",
                "kthreadd", "Xorg", "gnome-shell", "Spotlight", "ControlCenter", "coreaudiod",
                "corespotlightd", "backupd", "bird", "cloudd", "fileproviderd", "WallpaperAgent"}

_electron_cache = {}


def is_electron(bundle):
    if not bundle:
        return False
    if bundle not in _electron_cache:
        _electron_cache[bundle] = os.path.isdir(
            os.path.join(bundle, "Contents", "Frameworks", "Electron Framework.framework"))
    return _electron_cache[bundle]


def group_of(path):
    """Map an executable path to (group name, outermost .app bundle path or None)."""
    idx = path.find(".app/")
    if idx == -1 and path.endswith(".app"):
        idx = len(path) - 4
    if idx != -1:
        bundle = path[:idx + 4]
        return os.path.basename(bundle)[:-4], bundle
    base = os.path.basename(path) or path
    # Safari / WebKit tabs run as XPC services outside Safari.app.
    # (Networking/GPU helpers are shared with Mail etc., so only WebContent is attributed.)
    if base.startswith("com.apple.WebKit.WebContent") or base.startswith("com.apple.Safari"):
        return "Safari", "/Applications/Safari.app"
    return base, None


def classify(name, bundle):
    tags = []
    if name in BROWSERS:
        tags.append("browser")
    if VM_RE.search(name):
        tags.append("vm")
    if LLM_RE.match(name):
        tags.append("llm")
    if is_electron(bundle):
        tags.append("electron")
    if name in SYSTEM_NAMES or (bundle or "").startswith("/System/") or (not bundle and name.startswith("com.apple.")):
        tags.append("system")
    return tags


# --------------------------------------------------------------------------
# macOS collector
# --------------------------------------------------------------------------

def _num(s):
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


class MacCollector:
    name = "macOS"

    def __init__(self):
        s = self._sysctl(["hw.memsize", "hw.pagesize", "machdep.cpu.brand_string", "hw.model",
                          "kern.boottime"])
        self.total = int(s.get("hw.memsize", 0))
        self.pagesize = int(s.get("hw.pagesize", 16384))
        self.chip = s.get("machdep.cpu.brand_string") or s.get("hw.model") or "Mac"
        m = re.search(r"sec = (\d+)", s.get("kern.boottime", ""))
        self.boot = int(m.group(1)) if m else None
        prod = run(["sw_vers", "-productVersion"]).strip()
        self.os = "macOS " + prod if prod else "macOS"
        self.quittable = True

    @staticmethod
    def _sysctl(keys):
        out = run(["sysctl"] + keys)
        vals = {}
        for line in out.splitlines():
            if ": " in line:
                k, v = line.split(": ", 1)
                vals[k.strip()] = v.strip()
        return vals

    def counters(self):
        out = run(["vm_stat"])
        m = re.search(r"page size of (\d+) bytes", out)
        ps = int(m.group(1)) if m else self.pagesize
        vm = {}
        for line in out.splitlines():
            mm = re.match(r'^"?(.+?)"?:\s+(\d+)\.?$', line.strip())
            if mm:
                vm[mm.group(1)] = int(mm.group(2))
        s = self._sysctl(["vm.page_pageable_internal_count", "vm.page_purgeable_count",
                          "kern.memorystatus_vm_pressure_level", "kern.memorystatus_level",
                          "vm.swapusage"])
        purgeable = int(_num(s.get("vm.page_purgeable_count")) or vm.get("Pages purgeable", 0))
        internal = _num(s.get("vm.page_pageable_internal_count"))
        if internal is None:
            internal = vm.get("Anonymous pages", 0)
        # Activity Monitor's arithmetic.
        app = max(0, int(internal) - purgeable) * ps
        wired = vm.get("Pages wired down", 0) * ps
        compressed = vm.get("Pages occupied by compressor", 0) * ps
        stored = vm.get("Pages stored in compressor", 0) * ps
        cached = (vm.get("File-backed pages", 0) + purgeable) * ps
        used = app + wired + compressed
        free = max(0, self.total - used - cached)

        swap_total = swap_used = 0
        su = s.get("vm.swapusage", "")
        for key in ("total", "used"):
            mm = re.search(key + r" = ([\d.]+)([KMG])", su)
            if mm:
                v = float(mm.group(1)) * {"K": 1024, "M": MB, "G": GB}[mm.group(2)]
                if key == "total":
                    swap_total = v
                else:
                    swap_used = v

        lvl = int(_num(s.get("kern.memorystatus_vm_pressure_level")) or 1)
        level = {1: "normal", 2: "warn", 4: "critical"}.get(lvl, "normal")
        free_pct = _num(s.get("kern.memorystatus_level"))
        if free_pct is None:
            free_pct = 100.0 * (self.total - used) / self.total
        return {
            "app": app, "wired": wired, "compressed": compressed, "compressed_stored": stored,
            "cached": cached, "free": free, "used": used,
            "swap_total": swap_total, "swap_used": swap_used,
            "level": level, "free_pct": free_pct,
            "_cum": {
                "swapin": vm.get("Swapins", 0) * ps, "swapout": vm.get("Swapouts", 0) * ps,
                "pagein": vm.get("Pageins", 0) * ps, "pageout": vm.get("Pageouts", 0) * ps,
                "compress": vm.get("Compressions", 0) * ps, "decompress": vm.get("Decompressions", 0) * ps,
            },
        }

    def processes(self):
        # ps gives full executable paths and a decaying CPU average; top gives the
        # physical footprint ("Memory" column in Activity Monitor), which RSS undercounts.
        procs = {}
        for line in run(["ps", "-axo", "pid=,ppid=,%cpu=,rss=,comm="]).splitlines():
            parts = line.strip().split(None, 4)
            if len(parts) < 5:
                continue
            try:
                pid = int(parts[0])
                procs[pid] = {"pid": pid, "cpu": float(parts[2]), "bytes": int(parts[3]) * 1024,
                              "path": parts[4]}
            except ValueError:
                continue
        unit = {"B": 1, "K": 1024, "M": MB, "G": GB, "T": GB * 1024}
        seen_header = False
        for line in run(["top", "-l", "1", "-o", "mem", "-stats", "pid,mem"], timeout=15).splitlines():
            if not seen_header:
                seen_header = line.strip().startswith("PID")
                continue
            parts = line.split()
            if len(parts) < 2:
                continue
            mm = re.match(r"^([\d.]+)([BKMGT])", parts[1])
            try:
                pid = int(parts[0])
            except ValueError:
                continue
            if mm and pid in procs:
                procs[pid]["bytes"] = int(float(mm.group(1)) * unit[mm.group(2)])
        return list(procs.values())

    def quit_app(self, bundle):
        script = 'tell application "%s" to quit' % bundle.replace('"', '')
        r = subprocess.run(["osascript", "-e", script], stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, timeout=20)
        return r.returncode == 0, r.stderr.decode("utf-8", "replace").strip()


# --------------------------------------------------------------------------
# Linux collector
# --------------------------------------------------------------------------

class LinuxCollector:
    name = "Linux"

    def __init__(self):
        mi = self._meminfo()
        self.total = mi.get("MemTotal", 0)
        self.pagesize = os.sysconf("SC_PAGE_SIZE")
        chip = ""
        try:
            with open("/proc/cpuinfo") as f:
                for line in f:
                    if line.startswith("model name"):
                        chip = line.split(":", 1)[1].strip()
                        break
        except OSError:
            pass
        self.chip = chip or platform.machine()
        try:
            with open("/proc/uptime") as f:
                self.boot = int(time.time() - float(f.read().split()[0]))
        except OSError:
            self.boot = None
        self.os = "Linux " + platform.release()
        self.quittable = False

    @staticmethod
    def _meminfo():
        vals = {}
        try:
            with open("/proc/meminfo") as f:
                for line in f:
                    k, v = line.split(":", 1)
                    vals[k] = int(v.split()[0]) * 1024
        except OSError:
            pass
        return vals

    def counters(self):
        mi = self._meminfo()
        vm = {}
        try:
            with open("/proc/vmstat") as f:
                for line in f:
                    k, v = line.split()
                    vm[k] = int(v)
        except OSError:
            pass
        ps = self.pagesize
        total = mi.get("MemTotal", self.total)
        wired = (mi.get("KernelStack", 0) + mi.get("PageTables", 0) + mi.get("SUnreclaim", 0)
                 + mi.get("Unevictable", 0))
        compressed = mi.get("Zswap", 0)
        cached = max(0, mi.get("Cached", 0) + mi.get("Buffers", 0) + mi.get("SReclaimable", 0)
                     - mi.get("Shmem", 0))
        free = mi.get("MemFree", 0)
        app = max(0, total - wired - compressed - cached - free)
        avail = mi.get("MemAvailable", free + cached)
        free_pct = 100.0 * avail / total if total else 0
        psi = 0.0
        try:
            with open("/proc/pressure/memory") as f:
                mm = re.search(r"some avg10=([\d.]+)", f.read())
                psi = float(mm.group(1)) if mm else 0.0
        except OSError:
            pass
        level = "normal"
        if free_pct < 5 or psi > 10:
            level = "critical"
        elif free_pct < 15 or psi > 1:
            level = "warn"
        return {
            "app": app, "wired": wired, "compressed": compressed,
            "compressed_stored": mi.get("Zswapped", compressed),
            "cached": cached, "free": free, "used": app + wired + compressed,
            "swap_total": mi.get("SwapTotal", 0),
            "swap_used": mi.get("SwapTotal", 0) - mi.get("SwapFree", 0),
            "level": level, "free_pct": free_pct,
            "_cum": {
                "swapin": vm.get("pswpin", 0) * ps, "swapout": vm.get("pswpout", 0) * ps,
                "pagein": vm.get("pgpgin", 0) * 1024, "pageout": vm.get("pgpgout", 0) * 1024,
                "compress": vm.get("zswpout", 0) * ps, "decompress": vm.get("zswpin", 0) * ps,
            },
        }

    def processes(self):
        procs = []
        for line in run(["ps", "-eo", "pid=,ppid=,pcpu=,rss=,comm="]).splitlines():
            parts = line.strip().split(None, 4)
            if len(parts) < 5:
                continue
            try:
                procs.append({"pid": int(parts[0]), "cpu": float(parts[2]),
                              "bytes": int(parts[3]) * 1024, "path": parts[4]})
            except ValueError:
                continue
        return procs

    def quit_app(self, bundle):
        return False, "Quitting apps is only supported on macOS."


# --------------------------------------------------------------------------
# Sampler
# --------------------------------------------------------------------------

class Sampler:
    def __init__(self, collector):
        self.c = collector
        self.lock = threading.Lock()
        self.history = deque(maxlen=HISTORY_LEN)
        self.latest = None
        self.groups = []
        self.top = []
        self._prev_cum = None
        self._prev_t = None

    def start(self):
        self._sample_sys()
        self._sample_procs()
        threading.Thread(target=self._loop, args=(SYS_INTERVAL, self._sample_sys), daemon=True).start()
        threading.Thread(target=self._loop, args=(PROC_INTERVAL, self._sample_procs), daemon=True).start()

    @staticmethod
    def _loop(interval, fn):
        while True:
            t0 = time.time()
            try:
                fn()
            except Exception as e:  # keep sampling through transient failures
                print("sample error: %r" % (e,), file=sys.stderr)
            time.sleep(max(0.2, interval - (time.time() - t0)))

    def _sample_sys(self):
        now = time.time()
        c = self.c.counters()
        cum = c.pop("_cum")
        rates = {k: 0.0 for k in cum}
        if self._prev_cum is not None:
            dt = max(0.001, now - self._prev_t)
            rates = {k: max(0.0, (cum[k] - self._prev_cum[k]) / dt) for k in cum}
        self._prev_cum, self._prev_t = cum, now
        c["rates"] = rates
        c["t"] = now
        with self.lock:
            self.latest = c
            self.history.append({
                "t": round(now, 1), "app": c["app"], "wired": c["wired"],
                "compressed": c["compressed"], "cached": c["cached"], "used": c["used"],
                "swap_used": c["swap_used"], "free_pct": round(c["free_pct"], 1),
                "swapin": round(rates["swapin"]), "swapout": round(rates["swapout"]),
                "level": c["level"],
            })

    def _sample_procs(self):
        procs = self.c.processes()
        groups = {}
        for p in procs:
            name, bundle = group_of(p["path"])
            g = groups.get(name)
            if g is None:
                g = groups[name] = {"name": name, "bundle": bundle, "bytes": 0, "cpu": 0.0,
                                    "procs": 0, "pids": []}
            g["bytes"] += p["bytes"]
            g["cpu"] += p["cpu"]
            g["procs"] += 1
            g["pids"].append(p["pid"])
            if bundle and not g["bundle"]:
                g["bundle"] = bundle
        out = []
        for g in groups.values():
            g["tags"] = classify(g["name"], g["bundle"])
            g["cpu"] = round(g["cpu"], 1)
            g["quittable"] = bool(self.c.quittable and g["bundle"] and "system" not in g["tags"]
                                  and g["bundle"].startswith(("/Applications/", os.path.expanduser("~/Applications/"))))
            del g["pids"]
            out.append(g)
        out.sort(key=lambda g: g["bytes"], reverse=True)
        top = sorted(procs, key=lambda p: p["bytes"], reverse=True)[:15]
        for p in top:
            p["name"] = os.path.basename(p["path"]) or p["path"]
            p["group"] = group_of(p["path"])[0]
        with self.lock:
            self.groups = out
            self.top = top

    def snapshot(self):
        with self.lock:
            latest = dict(self.latest)
            history = list(self.history)
            groups = list(self.groups)
            top = list(self.top)
        c = self.c
        uptime = time.time() - c.boot if c.boot else None
        return {
            "host": socket.gethostname().split(".")[0], "os": c.os, "chip": c.chip,
            "total": c.total, "uptime": uptime, "quittable": c.quittable,
            "now": latest, "history": history, "groups": groups[:40], "top": top,
            "trend": trend(history, c.total),
            "insights": insights(latest, history, groups, c.total, uptime, c.name),
        }


def trend(history, total):
    """Least-squares slope of 'used' over the last 5 minutes → minutes until pressure."""
    pts = [h for h in history if h["t"] >= history[-1]["t"] - 300] if history else []
    if len(pts) < 10:
        return {"slope_mb_min": 0, "minutes_to_pressure": None, "state": "warming up"}
    t0 = pts[0]["t"]
    xs = [p["t"] - t0 for p in pts]
    ys = [p["used"] for p in pts]
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    den = sum((x - mx) ** 2 for x in xs) or 1
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / den  # bytes/s
    slope_mb_min = slope * 60 / MB
    ceiling = total * 0.9
    mins = None
    state = "stable"
    if slope_mb_min > 20:
        state = "climbing"
        mins = max(0, (ceiling - ys[-1]) / slope / 60)
    elif slope_mb_min < -20:
        state = "recovering"
    return {"slope_mb_min": round(slope_mb_min, 1),
            "minutes_to_pressure": round(mins, 1) if mins is not None else None, "state": state}


# --------------------------------------------------------------------------
# Insights
# --------------------------------------------------------------------------

def fmt(b):
    if b >= GB:
        return "%.1f GB" % (b / GB)
    return "%d MB" % round(b / MB)


def next_ram_tier(need):
    for tier in (8, 16, 18, 24, 32, 36, 48, 64, 96, 128, 192, 256):
        if tier * GB >= need:
            return tier
    return 256


def plan_text(plan, got, need):
    if not plan:
        return "Free about %s: close browser tabs first, then quit apps you are not using." % fmt(max(need, 1 * GB))
    names = ", ".join(g["name"] for g in plan)
    return "Free about %s. Quitting %s releases ~%s (these are idle right now)." % (
        fmt(max(need, 512 * MB)), names, fmt(got))


def insights(now, history, groups, total, uptime, platform_name):
    out = []

    def add(sev, title, detail, action=None, savings=0, apps=None):
        out.append({"severity": sev, "title": title, "detail": detail, "action": action,
                    "savings": savings, "apps": apps or []})

    recent = [h for h in history if h["t"] >= now["t"] - 60]
    # Fastest path back to comfortable headroom (~30% available): idle apps, biggest first.
    need = max(0.0, (0.30 - now["free_pct"] / 100.0) * total)
    plan, got = [], 0
    for g in groups:
        if got >= need:
            break
        if g["quittable"] and g["cpu"] < 1.0 and g["bytes"] > 200 * MB:
            plan.append(g)
            got += g["bytes"]
    swapout_60 = sum(h["swapout"] for h in recent) / max(1, len(recent))
    swapin_60 = sum(h["swapin"] for h in recent) / max(1, len(recent))
    level = now["level"]
    apps = [g for g in groups if "system" not in g["tags"]]

    # 1. Headline pressure status
    if level == "critical":
        add("critical", "Memory pressure is critical",
            "The kernel is out of cheap options: it is compressing and swapping at the same time, "
            "and apps stall while pages come back from disk. Free memory now, not later.",
            plan_text(plan, got, need), apps=[g["name"] for g in plan])
    elif level == "warn":
        add("serious", "Memory pressure is elevated",
            "RAM is oversubscribed. macOS is compressing aggressively and may be writing to swap. "
            "You will feel it when switching apps.",
            plan_text(plan, got, need), apps=[g["name"] for g in plan])
    else:
        add("good", "Memory pressure is normal",
            "%.0f%% of memory is available to apps without swapping. Nothing is urgent." % now["free_pct"])

    # 2. Active swapping
    if swapout_60 > 1 * MB or swapin_60 > 5 * MB:
        add("critical" if swapout_60 > 20 * MB else "serious",
            "Actively swapping: %s/s out, %s/s in" % (fmt(swapout_60), fmt(swapin_60)),
            "This is the lag you feel: every swap-in is a disk read on the critical path of an app "
            "you are using. It also burns SSD write endurance.",
            "Quit something heavy now; swapping stops within seconds of freeing memory.")

    # 3. Leftover swap
    if now["swap_used"] > 512 * MB and swapout_60 < 1 * MB:
        msg = ("%s is parked in swap from an earlier spike. It is harmless while it sits there, "
               "but anything it belongs to will stutter the next time you touch it." % fmt(now["swap_used"]))
        act = "Swap only shrinks when its owners exit. Quit and relaunch the apps you have kept open longest"
        if uptime and uptime > 7 * 86400:
            act += ", or restart (up %d days)." % (uptime // 86400)
        else:
            act += "."
        add("warning" if now["swap_used"] > 2 * GB else "info", "Stale swap: %s" % fmt(now["swap_used"]), msg, act)

    # 4. Compressor
    if now["compressed"] > 0.2 * total:
        ratio = now["compressed_stored"] / now["compressed"] if now["compressed"] else 0
        add("warning", "Compressor is holding %s" % fmt(now["compressed"]),
            "%s of app memory is squeezed into %s (%.1f:1). That is RAM you have already run out of; "
            "every access costs CPU to decompress." % (fmt(now["compressed_stored"]), fmt(now["compressed"]), ratio),
            "Closing the apps at the top of the list below frees the most compressed memory.")

    # 5. Browsers
    browsers = [g for g in groups if "browser" in g["tags"]]
    btotal = sum(g["bytes"] for g in browsers)
    if browsers and (btotal > 3 * GB or btotal > 0.2 * total):
        top_b = browsers[0]
        tips = [BROWSERS[g["name"]] for g in browsers if g["bytes"] > 500 * MB]
        add("warning" if btotal > 0.3 * total else "info",
            "Browsers are using %s (%d%% of RAM)" % (fmt(btotal), round(100 * btotal / total)),
            "%s alone is %s across %d processes — roughly one process per tab, extension and site. "
            "Tabs are the single biggest memory cost for most people." % (top_b["name"], fmt(top_b["bytes"]), top_b["procs"]),
            " ".join(tips) or "Close tabs you are not reading.", savings=int(btotal * 0.4))

    # 6. Electron
    electron = [g for g in groups if "electron" in g["tags"]]
    etotal = sum(g["bytes"] for g in electron)
    if len(electron) >= 2 and etotal > 1 * GB:
        names = ", ".join("%s (%s)" % (g["name"], fmt(g["bytes"])) for g in electron[:5])
        add("warning" if etotal > 3 * GB else "info",
            "%d Electron apps are using %s" % (len(electron), fmt(etotal)),
            "Each of these ships its own copy of Chromium: %s. Opening them as tabs in a browser you "
            "already run shares one engine instead of running several." % names,
            "Use the web versions (Slack, Discord, Notion, Teams all have them) or quit when idle.",
            savings=int(etotal * 0.6), apps=[g["name"] for g in electron if g["quittable"]])

    # 7. VMs / containers
    vms = [g for g in groups if "vm" in g["tags"] and g["bytes"] > 512 * MB]
    for g in vms[:2]:
        add("warning", "%s is reserving %s" % (g["name"], fmt(g["bytes"])),
            "A VM grabs its full memory allocation up front and rarely hands it back, even when your "
            "containers are idle.",
            "Lower the VM memory limit (Docker Desktop: Settings → Resources → Memory; OrbStack: "
            "Settings → System → Memory limit), or stop it when you are not using it.",
            savings=int(g["bytes"] * 0.5))

    # 8. Local LLMs
    for g in [g for g in groups if "llm" in g["tags"] and g["bytes"] > 1 * GB][:2]:
        add("warning", "%s has a model loaded (%s)" % (g["name"], fmt(g["bytes"])),
            "Model weights stay resident (and on Apple Silicon partly as wired GPU memory) until "
            "unloaded, whether or not you are chatting.",
            "Ollama: `ollama stop <model>` or set OLLAMA_KEEP_ALIVE=5m. LM Studio: eject the model.",
            savings=g["bytes"])

    # 9. Idle heavyweights
    idle = [g for g in apps if g["bytes"] > max(400 * MB, 0.03 * total) and g["cpu"] < 1.0
            and "vm" not in g["tags"] and "llm" not in g["tags"]]
    if idle:
        itotal = sum(g["bytes"] for g in idle)
        add("warning" if itotal > 0.15 * total else "info",
            "%d idle apps are holding %s" % (len(idle), fmt(itotal)),
            "Using under 1%% CPU but holding memory: %s. macOS will not reclaim this on its own; "
            "it only compresses it." % ", ".join("%s %s" % (g["name"], fmt(g["bytes"])) for g in idle[:6]),
            "Quit the ones you are not about to use. Reopening is faster than swapping.",
            savings=itotal, apps=[g["name"] for g in idle if g["quittable"]])

    # 10. Single giant
    for g in groups[:3]:
        if g["bytes"] > 0.25 * total and "browser" not in g["tags"] and "vm" not in g["tags"] \
                and "llm" not in g["tags"]:
            special = {
                "WindowServer": ("WindowServer draws every window. It grows with display count, "
                                 "scaled resolutions and open windows.",
                                 "Close windows you have minimized, drop a monitor or use a native resolution."),
                "kernel_task": ("kernel_task memory is wired: GPU buffers, drivers, file system caches.",
                                "Usually caused by VMs, external GPUs or heavy graphics apps."),
                "mds_stores": ("Spotlight is indexing. This is transient.",
                               "Leave it alone; it settles after indexing finishes."),
            }.get(g["name"], ("One process group owns a quarter of your RAM.",
                              "If it is not doing work you need right now, quit or restart it — "
                              "long-running apps leak."))
            add("warning", "%s is using %s (%d%%)" % (g["name"], fmt(g["bytes"]), round(100 * g["bytes"] / total)),
                special[0], special[1], savings=g["bytes"] if g["quittable"] else 0,
                apps=[g["name"]] if g["quittable"] else [])

    # 11. Wired
    if now["wired"] > 0.35 * total:
        add("warning", "Wired memory is %s" % fmt(now["wired"]),
            "Wired memory can never be compressed or swapped. On Apple Silicon, GPU allocations "
            "(games, ML models, pro video apps, many displays) count here.",
            "Check for VMs, local AI models and graphics-heavy apps.")

    # 12. Hardware verdict
    demand = now["used"] + now["swap_used"]
    if level != "normal" and demand > 1.3 * total:
        add("serious", "Your workload needs about %s; you have %s" % (fmt(demand), fmt(total)),
            "When demand exceeds physical RAM by 30%+ you are relying on swap for normal work. "
            "Tuning helps at the margin; it does not change that.",
            "Either trim the standing workload permanently or buy %d GB+ next time." % next_ram_tier(demand * 1.15))

    # 13. Long uptime
    if uptime and uptime > 14 * 86400 and platform_name == "macOS":
        add("info", "Up %d days" % (uptime // 86400),
            "Long uptimes accumulate leaked memory in background daemons and stale swap.",
            "Restart this week.")

    # 14. Cache myth-busting
    if now["cached"] > 0.2 * total and level == "normal":
        add("info", "%s of cached files is not a problem" % fmt(now["cached"]),
            "Cached files are recently used files kept in spare RAM. macOS evicts them instantly when "
            "apps need memory. Low 'free' memory is the system doing its job.",
            "Do not install 'RAM cleaner' apps or run `purge`; they throw away useful cache and make "
            "things slower.")

    rank = {"critical": 0, "serious": 1, "warning": 2, "good": 3, "info": 4}
    out.sort(key=lambda i: (rank[i["severity"]], -i["savings"]))
    return out


# --------------------------------------------------------------------------
# HTTP
# --------------------------------------------------------------------------

def make_handler(sampler, token, port):
    with open(os.path.join(HERE, "dashboard.html"), "rb") as f:
        page = f.read().replace(b"__MEMDASH_TOKEN__", token.encode())
    allowed_hosts = {"127.0.0.1:%d" % port, "localhost:%d" % port}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def _send(self, code, body, ctype="application/json"):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _host_ok(self):
            # Blocks DNS-rebinding: a hostile site's domain can't be pointed at us.
            return self.headers.get("Host") in allowed_hosts

        def do_GET(self):
            if not self._host_ok():
                return self._send(403, b"forbidden", "text/plain")
            if self.path in ("/", "/index.html"):
                return self._send(200, page, "text/html; charset=utf-8")
            if self.path == "/api/stats":
                return self._send(200, json.dumps(sampler.snapshot()).encode())
            self._send(404, b"not found", "text/plain")

        def do_POST(self):
            if not self._host_ok() or self.headers.get("X-Memdash-Token") != token:
                return self._send(403, b'{"ok":false,"error":"forbidden"}')
            if self.path != "/api/quit":
                return self._send(404, b'{"ok":false}')
            try:
                n = int(self.headers.get("Content-Length", "0"))
                name = json.loads(self.rfile.read(min(n, 4096)) or b"{}").get("name")
            except (ValueError, AttributeError):
                return self._send(400, b'{"ok":false,"error":"bad request"}')
            with sampler.lock:
                match = next((g for g in sampler.groups if g["name"] == name and g["quittable"]), None)
            if not match:
                return self._send(400, json.dumps({"ok": False, "error": "not a quittable app"}).encode())
            ok, err = sampler.c.quit_app(match["bundle"])
            self._send(200, json.dumps({"ok": ok, "error": err}).encode())

    return Handler


def main():
    ap = argparse.ArgumentParser(description="Live local memory dashboard.")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--no-open", action="store_true", help="don't open a browser")
    args = ap.parse_args()

    if sys.platform == "darwin":
        collector = MacCollector()
    elif sys.platform.startswith("linux"):
        collector = LinuxCollector()
    else:
        sys.exit("memdash supports macOS and Linux.")

    sampler = Sampler(collector)
    sampler.start()
    token = secrets.token_urlsafe(24)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(sampler, token, args.port))
    url = "http://127.0.0.1:%d/" % args.port
    print("memdash running at %s  (Ctrl+C to stop)" % url)
    if not args.no_open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
