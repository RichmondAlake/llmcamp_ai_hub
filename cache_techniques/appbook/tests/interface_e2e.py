"""Full Chromium interface checks, including live paid comparisons and experiments."""
import json
import os
import time
from pathlib import Path

from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "tests/artifacts"
ARTIFACTS.mkdir(parents=True, exist_ok=True)
URL = os.getenv("CACHE_APP_URL", "http://localhost:8033")
CHROME = os.getenv("CACHE_CHROME_PATH", "/Users/richmondalake/Library/Caches/ms-playwright/chromium-1223/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing")
report = json.loads((ARTIFACTS / "interface.json").read_text()) if os.getenv("CACHE_E2E_RESUME") else {"checks": [], "page_errors": [], "experiments": []}


def checked(name):
    report["checks"].append(name)
    (ARTIFACTS / "interface.json").write_text(json.dumps(report, indent=2))
    print(name, flush=True)


def response_for(page, path, click):
    with page.expect_response(lambda r: r.url.endswith(path) and r.request.method == "POST", timeout=180000) as response:
        click()
    value = response.value.json()
    assert response.value.ok, value
    return value


def run_done(page, expected_rows=None):
    last = None
    deadline = time.monotonic() + 900
    while time.monotonic() < deadline:
        status = page.locator("#job-status").inner_text()
        if status != last:
            print(status, flush=True)
            last = status
        if status.startswith(("completed", "cancelled", "failed", "interrupted")):
            break
        page.wait_for_timeout(1000)
    else:
        raise AssertionError("Experiment failed to finish in 15 minutes")
    job_id = page.evaluate("localStorage.getItem('cache-job')")
    job = page.request.get(URL + "/api/tokenomics/" + job_id).json()
    assert job["status"] in {"completed", "cancelled"}, job.get("error")
    assert all(row["status"] == "success" for row in job["rows"]), [r.get("error") for r in job["rows"]]
    if expected_rows is not None:
        assert len(job["rows"]) == expected_rows
        assert job["status"] == "completed"
    report["experiments"].append({"id": job_id, "status": job["status"], "rows": len(job["rows"]), "cache_read_tokens": sum(r["cache_read_tokens"] for r in job["rows"])})
    return job


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=CHROME, headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 1000}, reduced_motion="reduce", accept_downloads=True)
        page = context.new_page()
        page.on("pageerror", lambda error: report["page_errors"].append(str(error)))
        page.goto(URL)
        expect(page.locator("#provider-status")).to_have_text("Oracle · connected", timeout=30000)
        expect(page.locator(".tech-card")).to_have_count(6)
        page.screenshot(path=str(ARTIFACTS / "overview.png"), full_page=True)
        checked("Overview, live status and all six cache interfaces")

        if os.getenv("CACHE_E2E_RESUME"):
            page.goto(URL + "/#tokenomics")
            expect(page.locator("#saved-run")).to_be_visible()
            page.locator("#saved-run").select_option(os.environ["CACHE_E2E_RESUME"])
            expect(page.locator("#job-status")).to_contain_text("completed · 36/36")
            cumulative = run_done(page, 36)
        else:
            # A new sandbox changes namespaces, preserving the shared authored corpus.
            before = page.request.get(URL + "/api/status").json()["workspace"]
            sandbox = response_for(page, "/api/sandbox", lambda: page.locator("#new-sandbox").click())
            assert sandbox["workspace"] != before
            checked("New sandbox starts with separate cache namespaces")

            queries = {
                "normal": "Explain why an exact response cache needs a TTL.",
                "embedding": "A semantic cache retrieves previously generated answers.",
                "semantic": "Explain how semantic caching helps agent memory.",
                "prompt": "Explain embedding caching in two sentences.",
                "tool": "Oracle AI Database HNSW vector search official documentation",
                "unified": "Explain how semantic caching helps agent memory.",
            }
            for mechanism, query in queries.items():
                page.goto(URL + "/#cache/" + mechanism)
                expect(page.locator("#shared-query")).to_be_visible()
                expect(page.locator("#provider-status")).to_have_text("Oracle · connected")
                page.locator("#shared-query").fill(query)
                first = response_for(page, "/api/compare/" + mechanism, lambda: page.locator("#compare").click())
                assert first["with"]["status"] == first["without"]["status"] == "success"
                assert first["with"]["metrics"]["provider_calls"] == (0 if mechanism == "embedding" else 1)
                expect(page.locator("#comparison-status")).to_contain_text("Measured execution")
                warm = response_for(page, "/api/compare/" + mechanism, lambda: page.locator("#repeat").click())
                assert warm["with"]["hit"] == ("normal" if mechanism == "unified" else mechanism), warm["with"]
                expect(page.locator("#pane-with .cache-badge")).to_contain_text("HIT")
                if mechanism == "embedding":
                    expect(page.locator("canvas.vector-grid")).to_have_count(2)
                    assert first["with"]["vector"] == warm["with"]["vector"]
                    page.locator("#vector-with").hover(position={"x": 30, "y": 30})
                    expect(page.locator("#vector-with")).to_have_attribute("title", __import__('re').compile("Dimension"))
                elif mechanism == "prompt":
                    assert warm["with"]["metrics"]["cache_read_tokens"] >= 512
                    page.locator(".prefix-window summary").click()
                    expect(page.locator(".prompt-text")).to_contain_text("Authored course context")
                    page.screenshot(path=str(ARTIFACTS / "prompt_cache.png"), full_page=True)
                elif mechanism == "tool":
                    assert first["with"]["collected_at"] == warm["with"]["collected_at"]
                    assert warm["with"]["metrics"]["tool_calls"] == 0
                    page.locator("#pane-with details summary").click()
                    assert page.locator("#pane-with .source-item a").count() > 0
                elif mechanism == "unified":
                    expect(page.locator("#stack-options .option-hint small")).to_have_count(5)
                    assert first["with"]["embedding_hits"] >= 1
                    assert warm["with"]["embedding_hits"] == 0
                checked(mechanism + ": live cold/warm paired interface and actual usage")

            # A deliberately broader, explicit threshold (MiniLM puts this paraphrase ~0.29 away) plus
            # the reranker check demonstrates a real paraphrase hit.
            page.goto(URL + "/#cache/semantic")
            # Wait for the page to restore the previous comparison; it rewrites the settings when it does.
            expect(page.locator("#comparison-status")).to_contain_text("Measured execution", timeout=30000)
            page.locator(".cache-settings summary").click()
            page.locator("#compare-threshold").fill("0.35")
            page.locator("#shared-query").fill(queries["semantic"])
            response_for(page, "/api/compare/semantic", lambda: page.locator("#compare").click())
            page.locator("#alternative").click()
            match = response_for(page, "/api/compare/semantic", lambda: page.locator("#compare").click())
            assert match["with"]["hit"] == "semantic"
            assert 0 < match["with"]["distance"] <= 0.35
            assert match["with"]["rerank_score"] >= 0
            expect(page.locator("#comparison-status")).to_contain_text("0.35")
            page.screenshot(path=str(ARTIFACTS / "semantic_cache.png"), full_page=True)
            checked("Semantic paraphrase matching with visible distance and explicit threshold")

            # Vector-space viewer: examples, a chosen query, the policy's verdict and the distance calculation.
            expect(page.locator("#vs-canvas")).to_be_visible()
            page.locator("#vs-load").click()
            expect(page.locator("#vs-count")).to_contain_text("examples", timeout=30000)
            page.locator("#compare-threshold").fill("0.10")
            page.locator("[data-example]").first.click()
            expect(page.locator(".vs-decision")).to_contain_text("Semantic hit", timeout=30000)
            page.locator("[data-example]").nth(3).click()
            expect(page.locator(".vs-decision")).to_contain_text("Miss", timeout=30000)
            page.locator("#vs-neighbors .neighbor-button").first.click()
            expect(page.locator("#vs-cosine")).not_to_have_text("—")
            page.locator("#vector-space").screenshot(path=str(ARTIFACTS / "vector_space.png"))
            checked("Vector-space viewer: examples, query placement, cache verdict and per-dimension distance")

            page.locator("#explorer-toggle").click()
            expect(page.locator("[data-table='CT_VECTOR_EXAMPLES']")).to_be_visible(timeout=15000)
            page.locator("[data-table='CT_VECTOR_EXAMPLES']").click()
            page.locator("#table-grid tbody tr").first.click()
            expect(page.locator("#row-inspector")).to_contain_text("VECTOR(384, FLOAT32)")
            page.screenshot(path=str(ARTIFACTS / "data_explorer.png"))
            page.locator("#explorer-toggle").click()
            checked("Read-only data explorer lists the cache tables and inspects rows")

            page.goto(URL + "/#cache/unified")
            page.locator("#request-kind").select_option("live")
            page.locator("#shared-query").fill(queries["tool"])
            first = response_for(page, "/api/compare/unified", lambda: page.locator("#compare").click())
            warm = response_for(page, "/api/compare/unified", lambda: page.locator("#repeat").click())
            assert warm["with"]["reuse_eligible"] is False
            assert warm["with"]["metrics"]["provider_calls"] == 1
            assert warm["with"]["metrics"]["tool_calls"] == 0
            assert "tool" in warm["with"]["cache_hits"] and "prompt" in warm["with"]["cache_hits"]
            checked("Unified live path bypasses answers and exposes tool plus prompt hits")

            # Navigate while a provider call is in flight: late completion must not touch removed nodes.
            page.goto(URL + "/#cache/normal")
            page.locator("#shared-query").fill("Explain memory cache capacity in two sentences.")
            with page.expect_response(lambda r: r.url.endswith("/api/compare/normal") and r.request.method == "POST", timeout=180000) as late:
                page.locator("#compare").click()
                page.evaluate("location.hash='architecture'")
            assert late.value.ok
            expect(page.locator("#architecture-kind")).to_be_visible()
            checked("Navigation during a live request preserves the current interface")

            for mechanism in [*queries, "baseline"]:
                page.locator("#architecture-kind").select_option(mechanism)
                expect(page.locator(".ra-svg")).to_be_visible()
                for request_kind in ["explanation", "live"]:
                    valid = page.evaluate("""([kind,path])=>{const s=cacheArchitecture(kind,{normal:true,embedding:true,semantic:true,prompt:true,tool:true},path),ids=new Set(s.components.map(c=>c.id)),flows=new Set(s.flows.map(f=>f.id));return s.flows.every(f=>ids.has(f.from)&&ids.has(f.to))&&s.runs.every(r=>r.steps.every(t=>flows.has(t.flow)));}""", [mechanism, request_kind])
                    assert valid
                page.locator(".ra-node").first.click()
                expect(page.locator("#ra-detail")).to_contain_text("Shared request")
                page.locator("#ra-step").click()
                expect(page.locator("#ra-now")).to_contain_text("Step 1")
                page.wait_for_timeout(100)
                page.locator("#ra-reset").click()
                expect(page.locator("#ra-now")).not_to_contain_text("Step 1")
            page.locator("#architecture-kind").select_option("unified")
            page.locator("#architecture-request").select_option("live")
            assert page.locator(".ra-node[data-node='semantic']").count() == 0
            page.locator("#ra-run").select_option("tool-hit")
            page.locator("#ra-speed").fill("4")
            page.locator("#ra-play").click()
            expect(page.locator("#ra-now")).to_contain_text("done", timeout=15000)
            page.locator("#ra-fit").click()
            expect(page.locator("#ra-fit")).to_have_attribute("aria-pressed", "true")
            page.screenshot(path=str(ARTIFACTS / "architecture_live.png"), full_page=True)
            checked("All architecture variants, valid flow paths, component inspection and simulation controls")

            page.goto(URL + "/#tokenomics")
            page.locator("#workload-mode").select_option("custom")
            page.locator("#turns").fill("2")
            page.locator("#custom-inputs").fill("Explain memory caching.")
            with page.expect_response(lambda r: r.url.endswith("/api/workloads")) as invalid:
                page.locator("#preview-workload").click()
            assert invalid.value.status == 409
            expect(page.locator("#run-experiment")).to_be_disabled()
            page.locator("#workload-mode").select_option("scenario")
            for scenario in ["repeat", "diverse", "invalidation", "mixed"]:
                page.locator("#scenario").select_option(scenario)
                page.locator("#turns").fill("6")
                workload = response_for(page, "/api/workloads", lambda: page.locator("#preview-workload").click())
                assert len(workload["requests"]) == 6
                expect(page.locator(".workload-list li")).to_have_count(6)
                if scenario in {"diverse", "invalidation"}:
                    assert len({r["query"] for r in workload["requests"]}) == 6
            checked("Scenario previews evolve; custom turn-count mismatches are rejected")
            page.locator(".cache-settings summary").click()
            page.locator("#experiment-ttl").fill("600")
            page.locator("#experiment-tool-ttl").fill("300")
            started = response_for(page, "/api/tokenomics", lambda: page.locator("#run-experiment").click())
            expect(page.locator("#run-experiment")).to_be_disabled()
            # Exercise polling cleanup and restoring the active run by ID.
            page.evaluate("location.hash='architecture'")
            expect(page.locator("#architecture-kind")).to_be_visible()
            page.evaluate("location.hash='tokenomics'")
            expect(page.locator("#job-status")).to_be_visible(timeout=10000)
            cumulative = run_done(page, 36)
        assert sum(r["cache_read_tokens"] for r in cumulative["rows"]) > 0
        assert any("embedding" in r["cache_hits"] for r in cumulative["rows"])
        assert any("tool" in r["cache_hits"] for r in cumulative["rows"])
        (ARTIFACTS / "cumulative_experiment.json").write_text(json.dumps(cumulative, indent=2))
        expect(page.locator(".cache-chart")).to_have_count(4)
        for button in page.locator(".lane-toggle").all():
            button.click()
        assert page.locator(".cache-chart [data-series]").count() == 0
        page.locator(".lane-toggle").first.click()
        assert page.locator(".cache-chart [data-series='baseline']").count() > 0
        while page.locator(".lane-toggle[aria-pressed=false]").count():
            page.locator(".lane-toggle[aria-pressed=false]").first.click()
        with page.expect_download() as download:
            page.locator("#export-run").click()
        download.value.save_as(ARTIFACTS / "exported_experiment.json")
        assert len(json.loads((ARTIFACTS / "exported_experiment.json").read_text())["rows"]) == 36
        page.locator(".cache-history > summary").click()
        page.locator(".experiment-row > summary").first.click()
        page.screenshot(path=str(ARTIFACTS / "tokenomics.png"), full_page=True)
        checked("36-request live cumulative experiment, four charts, legend toggles, turn inspection and export")

        page.locator("#comparison-mode").select_option("individual")
        page.locator("#comparison-mode").select_option("custom")
        expect(page.locator("#custom-options .option-hint small")).to_have_count(5)
        for checkbox in page.locator("#custom-options input").all():
            checkbox.uncheck()
        page.locator("#workload-mode").select_option("synthetic")
        page.locator("#turns").fill("2")
        page.locator("#synthetic-focus").fill("Explain embedding caching, then repeat exactly that question.")
        synthetic = response_for(page, "/api/workloads", lambda: page.locator("#preview-workload").click())
        assert synthetic["generation"]["provider_calls"] == 1
        assert synthetic["generation"]["estimated_usd"] > 0
        response_for(page, "/api/tokenomics", lambda: page.locator("#run-experiment").click())
        custom = run_done(page, 4)
        assert all(not value for value in custom["lanes"][1]["features"].values())
        assert all(r["hit"] is None for r in custom["rows"])
        checked("Claude-generated reviewed workload, separate generation cost and all-off custom stack")

        page.locator("#workload-mode").select_option("scenario")
        page.locator("#scenario").select_option("repeat")
        page.locator("#turns").fill("3")
        response_for(page, "/api/workloads", lambda: page.locator("#preview-workload").click())
        response_for(page, "/api/tokenomics", lambda: page.locator("#run-experiment").click())
        response_for(page, "/api/tokenomics/" + page.evaluate("localStorage.getItem('cache-job')") + "/cancel", lambda: page.locator("#cancel-run").click())
        cancelled = run_done(page)
        assert cancelled["status"] == "cancelled" and len(cancelled["rows"]) < 6
        checked("Stop button preserves completed paid measurements")

        page.reload()
        expect(page.locator("#saved-run")).to_be_visible()
        page.locator("#saved-run").select_option(cumulative["id"])
        expect(page.locator("#job-status")).to_contain_text("completed · 36/36")
        checked("Saved experiments reload and switch without rerunning providers")

        # A clean browser can also discover the durable runs without localStorage.
        mobile = browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, reduced_motion="reduce")
        phone = mobile.new_page()
        phone.on("pageerror", lambda error: report["page_errors"].append(str(error)))
        for route in ["overview", "cache/embedding", "cache/unified", "architecture", "tokenomics"]:
            phone.goto(URL + "/#" + route)
            expect(phone.locator("#provider-status")).to_have_text("Oracle · connected")
            phone.wait_for_timeout(400)
            width = phone.evaluate("({scroll:document.documentElement.scrollWidth,viewport:innerWidth})")
            assert width["scroll"] <= width["viewport"] + 2, (route, width)
        expect(phone.locator("#saved-run")).to_be_visible()
        phone.locator("#saved-run").select_option(cumulative["id"])
        expect(phone.locator("#job-status")).to_contain_text("completed · 36/36")
        phone.locator("#theme").click()
        assert phone.locator("html").get_attribute("data-theme") == "light"
        phone.screenshot(path=str(ARTIFACTS / "mobile_tokenomics.png"), full_page=True)
        phone.locator("#menu").click()
        expect(phone.locator("#sidebar")).to_have_class(__import__('re').compile("open"))
        checked("Mobile layout, navigation, light theme and fresh-browser experiment discovery")
        assert not report["page_errors"], report["page_errors"]
        checked("No JavaScript page errors across desktop/mobile, requests and live experiment navigation")
        browser.close()


if __name__ == "__main__":
    main()
