# memdash — live memory dashboard

This is Activity Monitor's Memory tab in more detail, laid out like a car's battery screen. It also tells you what to do about what it shows.

```bash
python3 tools/memdash/memdash.py          # opens http://127.0.0.1:8765
python3 tools/memdash/memdash.py --port 9000 --no-open
```

It needs no installs: Python 3.8+ standard library only (macOS ships `python3` with the Xcode command-line tools). Leave the page open and it updates every 2 s, keeping 30 minutes of history while the script runs.

## What it shows

| Panel | Source (macOS) |
|---|---|
| **Available %**: the battery charge | `kern.memorystatus_level`, the kernel's own "memory free" figure |
| **Pressure** gauge + status | `kern.memorystatus_vm_pressure_level` (normal / warn / critical, same as Activity Monitor's graph colour) |
| App / Wired / Compressed / Cached | `vm_stat` + `vm.page_pageable_internal_count` / `vm.page_purgeable_count`, using the same arithmetic Activity Monitor uses |
| Compression ratio | pages *stored* in the compressor ÷ pages it *occupies* |
| Swap used + swap in/out, compress/decompress rates | `vm.swapusage`, deltas of `vm_stat` counters |
| Trend ("≈ N min to 90% full") | least-squares slope of Memory Used over the last 5 min |
| Apps by memory | `top` physical footprint (Activity Monitor's *Memory* column) grouped by owning `.app` bundle, so Chrome's 30 helpers show up as one "Google Chrome" row |

## Insights

These are rule-based and recomputed every refresh. They include:

- **Actively swapping**: the real cause of lag. It ignores "swap used" that is just sitting there.
- **Fastest path back to green**: how much to free, and exactly which *idle* apps (under 1% CPU) would free it.
- **Idle heavyweights**: apps holding memory while doing nothing, each with a one-click **Quit**.
- **Browsers**: total across all helper processes, with browser-specific settings (Chrome Memory Saver, Edge sleeping tabs, Firefox `about:unloads`, …).
- **Electron apps**: each bundles its own Chromium, and the card shows their total.
- **VMs / Docker / OrbStack** and **local LLMs** (Ollama, LM Studio) holding reserved memory.
- Heavy **compressor** use, high **wired** memory, **stale swap**, long **uptime**.
- **Your workload exceeds your RAM**: shown when demand (used + swap) is more than 1.3× physical RAM, with the RAM tier to buy next.
- A reminder that **cached files are not a problem** and "RAM cleaner" apps make things worse.

## Safety

- It binds to `127.0.0.1` only and rejects requests with a foreign `Host` header, which blocks DNS rebinding.
- **Quit** sends the app a normal `quit` Apple Event, so the app still prompts to save. It never force-kills anything. The endpoint needs a random per-run token embedded in the page, and it only accepts apps from `/Applications` or `~/Applications` that appeared in the latest sample. System processes can't be quit.
- Nothing is written to disk and nothing leaves the machine.

## Linux

It also runs on Linux using `/proc/meminfo`, `/proc/vmstat` and PSI (`/proc/pressure/memory`). There, "Compressed" means zswap, and Quit is disabled.
