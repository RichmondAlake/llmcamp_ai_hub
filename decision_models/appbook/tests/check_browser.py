"""Browser checks: every page at desktop and phone width, plus the main interactions.

    ./run.sh &                                       # in another terminal
    ../.venv/bin/python tests/check_browser.py       # BASE=http://127.0.0.1:8740 by default

Screenshots go to tests/artifacts/ (gitignored). Uses Jev for the live interactions when it has a
key, so the check is quick and does not need the local model.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = os.environ.get("BASE", "http://127.0.0.1:8740")
OUT = Path(__file__).resolve().parent / "artifacts"
#: Lets a full-page screenshot see the whole stage, which otherwise scrolls inside its own panel.
UNROLL = ".app{height:auto!important}.stage{height:auto!important;overflow:visible!important}.data-explorer{display:none!important}"
PAGES = ["", "chunking", "reranking", "cache", "routing", "consolidation", "extraction", "tools", "scoreboard", "providers", "tokenomics"]
results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))
    print(f"{'PASS' if ok else 'FAIL'}  {name}  {detail}", flush=True)


def main() -> int:
    OUT.mkdir(exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for label, size in (("desktop", {"width": 1440, "height": 900}), ("phone", {"width": 390, "height": 844})):
            page = browser.new_page(viewport=size)
            errors: list[str] = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
            page.goto(f"{BASE}/")
            page.evaluate("localStorage.setItem('dm-models', JSON.stringify(['jev']))")
            page.reload()
            for name in PAGES:
                page.goto(f"{BASE}/#/{name}")
                page.wait_for_selector(".view .eval-title", timeout=15000)
                page.wait_for_timeout(1200)
                title = page.inner_text(".view .eval-title")
                overflow = page.evaluate("document.querySelector('.view').scrollWidth > document.querySelector('.stage').clientWidth + 2")
                check(f"{label} {name or 'architecture'}", bool(title) and not overflow, title[:60] + (" · overflows" if overflow else ""))
                style = page.add_style_tag(content=UNROLL)
                page.screenshot(path=str(OUT / f"{label}-{name or 'architecture'}.png"), full_page=True)
                style.evaluate("el => el.remove()")
            check(f"{label} console clean", not errors, "; ".join(errors[:3]))
            page.close()

        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.goto(f"{BASE}/")
        page.evaluate("localStorage.setItem('dm-models', JSON.stringify(['jev']))")
        page.reload()
        page.goto(f"{BASE}/#/")
        page.wait_for_selector(".dp[data-n='19']")
        page.click(".dp[data-n='19']")
        page.wait_for_timeout(400)
        check("architecture: a point opens its detail", "Tool and skill selection" in page.inner_text("#arch-detail"))
        hot = page.eval_on_selector_all("#arch-stores .mem.hot", "els => els.map(e => e.dataset.store)")
        check("architecture: the point lights its store", hot == ["procedural"], str(hot))
        chips = page.eval_on_selector_all("#arch-swaps .swap-chip", "els => els.length")
        check("architecture: the seven swaps are listed", chips == 7, str(chips))
        style = page.add_style_tag(content=UNROLL)
        page.screenshot(path=str(OUT / "interaction-architecture-19.png"), full_page=True)
        style.evaluate("el => el.remove()")

        page.goto(f"{BASE}/#/cache")
        page.wait_for_selector(".verdict .vword")
        check("cache: the verdict comes first", page.inner_text(".verdict .vword").strip().lower().endswith("better"), page.inner_text(".verdict .vword"))
        page.wait_for_selector("#sw-chart svg", timeout=30000)
        check("cache: the threshold chart draws", True)
        page.click(".examples .ex[data-i='0']")
        page.wait_for_selector("#sw-out .acard", timeout=60000)
        cards = page.eval_on_selector_all("#sw-out .acard h3", "els => els.map(e => e.innerText.trim().split('\\n')[0])")
        out = page.inner_text("#sw-out").lower()
        check("cache: today and Jev answer the near miss", len(cards) == 2 and "miss" in out and "right answer" in out, str(cards))
        page.wait_for_timeout(800)
        check("model context rail shows the request", "request as sent" in page.inner_text("#ctxrail"))
        style = page.add_style_tag(content=UNROLL)
        page.screenshot(path=str(OUT / "interaction-cache.png"), full_page=True)
        style.evaluate("el => el.remove()")

        page.goto(f"{BASE}/#/tools")
        page.wait_for_selector(".examples .ex")
        page.click(".examples .ex[data-i='0']")
        page.wait_for_selector("#sw-out .acard", timeout=60000)
        wrong = page.eval_on_selector_all("#sw-out .acard.is-wrong", "els => els.length")
        right = page.eval_on_selector_all("#sw-out .acard.is-right", "els => els.length")
        check("tools: today is wrong and Jev is right on the Q3 report", wrong == 1 and right == 1, f"wrong {wrong}, right {right}")

        page.goto(f"{BASE}/#/consolidation")
        page.wait_for_selector("#sw-set-run")
        page.select_option("#sw-set-model", "jev")
        page.click("#sw-set-run")
        page.wait_for_selector("#sw-set-out table", timeout=120000)
        check("consolidation: the labelled set runs live", "right action" in page.inner_text("#sw-set-out").lower())
        style = page.add_style_tag(content=UNROLL)
        page.screenshot(path=str(OUT / "interaction-consolidation.png"), full_page=True)
        style.evaluate("el => el.remove()")

        page.goto(f"{BASE}/#/scoreboard")
        page.wait_for_selector(".sb-row")
        rows = page.eval_on_selector_all(".sb-row", "els => els.length")
        check("scoreboard: seven rows", rows == 7, str(rows))

        page.goto(f"{BASE}/#/providers")
        page.wait_for_selector("#pv-run")
        page.click("#pv-run")
        page.wait_for_selector("#pv-out .acard", timeout=60000)
        check("playground: answers", "billing" in page.inner_text("#pv-out"))

        page.click("#explorer-toggle")
        page.wait_for_selector("#explorer-table-list [data-t='labels_memory_routing']")
        page.click("#explorer-table-list [data-t='labels_memory_routing']")
        page.wait_for_function("document.querySelector('#explorer-table-name').textContent === 'labels_memory_routing'")
        check("data explorer reads a table", " ".join(page.inner_text("#explorer-page").split()) == "1–40 of 58", page.inner_text("#explorer-page"))
        page.screenshot(path=str(OUT / "interaction-explorer.png"))
        browser.close()

    failed = [n for n, ok, _ in results if not ok]
    print(f"\n{len(results) - len(failed)} of {len(results)} passed" + (f"; failed: {failed}" if failed else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
