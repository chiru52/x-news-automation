"""News History uses a dedicated, read-only Archive sidebar view."""
import re
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

class HistoryUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.page=(ROOT/"dashboard/index.html").read_text("utf-8")
        cls.js=(ROOT/"dashboard/app.js").read_text("utf-8")
        cls.worker=(ROOT/"news-collector/worker.mjs").read_text("utf-8")
        cls.archive=(ROOT/"news-collector/archive.mjs").read_text("utf-8")
        cls.client=(ROOT/"dashboard/archive-client.mjs").read_text("utf-8")

    def test_compact_source_health_panel_uses_public_diagnostics(self):
        self.assertIn('id="source-health"',self.page)
        self.assertIn('id="source-health-summary"',self.page)
        self.assertIn('id="source-health-list"',self.page)
        self.assertIn('source_health:dynamic.source_health',self.js)
        self.assertIn('row.textContent=source.name',self.js)
        self.assertIn('source_health:{checked_at:',self.worker)

    def test_history_has_last_sidebar_menu(self):
        nav=self.page.split('<nav class="nav-items" aria-label="Main navigation">',1)[1].split("</nav>",1)[0]
        self.assertEqual(re.findall(r'data-view="([^"]+)"',nav),
                         ["all","trending","global","india","workflow","copied","saved","archive"])
        for field in ("archive-toggle","archive-controls","archive-days",
                      "archive-date","archive-region","archive-publisher",
                      "archive-search","archive-status","archive-prev","archive-next"):
            self.assertIn(f'id="{field}"',self.page)
        self.assertIn('function archiveMode() {return selectedView === "archive" && historyOpen;}',self.js)
        self.assertIn('"archive-controls").hidden = !archiveMode()',self.js)

    def test_archive_optional_stats_never_block_article_results(self):
        self.assertIn("const validStats=stats",self.js)
        self.assertIn('if(validStats)',self.js)
        self.assertIn('$("archive-statistics").hidden=true',self.js)
        self.assertNotIn('throw Error("Invalid archive statistics")',self.js)
        self.assertIn(r'/^\d{4}-\d{2}-\d{2}$/.test(stats.earliest_date)',self.js)

    def test_archive_clear_filters_resets_all_controls_without_navigation(self):
        self.assertIn('id="archive-clear-filters"', self.page)
        section=self.js.split('$("archive-clear-filters").addEventListener("click",()=>{',1)[1].split('\n});',1)[0]
        for control in ('search-input', 'archive-days', 'archive-date', 'archive-region', 'archive-publisher'):
            self.assertIn(f'$("{control}").value=',section)
        self.assertIn('selectedCategory="all"',section)
        self.assertIn('loadHistory(0)',section)
        self.assertNotIn('setView(',section)

    def test_archive_layout_hides_duplicate_global_metrics_only_in_archive(self):
        self.assertIn('id="dashboard-intro"',self.page)
        self.assertIn('id="dashboard-metrics"',self.page)
        self.assertIn('id="archive-statistics"',self.page)
        self.assertIn('$("dashboard-metrics").hidden = archiveMode()',self.js)
        self.assertIn('$("dashboard-intro").hidden = archiveMode()',self.js)

    def test_archive_is_deliberate_fetch_only_without_background_polling(self):
        self.assertIn('async function loadHistory(page=0)',self.js)
        self.assertIn('fetch(url,{cache:"no-store",credentials:"omit",mode:"cors"})',self.js)
        self.assertIn('$("archive-search").addEventListener("click",()=>loadHistory(0))',self.js)
        self.assertIn('if(archiveMode())',self.js)
        self.assertIn('archiveResponse(data)',self.js)
        self.assertNotIn('method:"POST"',self.js)
        self.assertNotIn('api.x.com',self.js)
        self.assertIn('import {archiveEndpoint, archiveQuery, archiveResponse}',self.js)

    def test_worker_archive_is_get_only_and_falls_back_safely(self):
        self.assertIn('if (u.pathname==="/archive")',self.worker)
        self.assertIn('historyParams(u)',self.worker)
        self.assertIn('queryArchive(buckets,params)',self.worker)
        self.assertIn('ARCHIVE_TTL_SECONDS',self.worker)
        self.assertIn('await env.NEWS_CACHE.put(SNAPSHOT_KEY,JSON.stringify(data));',self.worker)
        self.assertIn('archive_written=false',self.worker)
        self.assertIn('if (request.method!=="GET" && request.method!=="HEAD")',self.worker)
        self.assertIn("MAX_PER_DAY=120",self.archive)
        self.assertIn("ARCHIVE_DAYS=30",self.archive)

    def test_public_build_contains_browser_module(self):
        exporter=(ROOT/"newsbot/dashboard_export.py").read_text("utf-8")
        workflow=(ROOT/".github/workflows/build-news-dashboard.yml").read_text("utf-8")
        self.assertIn('"archive-client.mjs"',exporter)
        self.assertIn("node --test tests/signaldesk-news-history.test.mjs",workflow)
        self.assertIn("PUBLISH_ENABLED: 'false'",workflow)
        self.assertNotIn("api.openai.com",self.client)


if __name__=="__main__":
    unittest.main()
