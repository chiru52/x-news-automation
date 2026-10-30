#!/usr/bin/env bash
# PREVIEW ONLY. Do not configure this as the production build until private
# editorial draft migration and feed continuity are explicitly approved.
set -euo pipefail
if [[ "${SIGNALDESK_PREVIEW_BUILD:-}" != "true" ]]; then
  echo "Refusing to build: set SIGNALDESK_PREVIEW_BUILD=true for a preview only." >&2
  exit 1
fi
export PUBLISH_ENABLED=false
python3 -m newsbot --preview --dashboard-limit 30 --output output/dashboard-news
printf '[]\n' > output/dashboard-news/empty-issues.json
python3 -m newsbot.dashboard_export \
  --queue output/dashboard-news/review_queue.json \
  --issues-file output/dashboard-news/empty-issues.json \
  --output dist/signaldesk
python3 -m news_collector.configure_live dist/signaldesk
python3 - <<'PY'
import json
from pathlib import Path
from newsbot.dashboard_export import validate_public_bundle
root = Path("dist/signaldesk")
data = json.loads((root / "data.json").read_text(encoding="utf-8"))
validate_public_bundle(data)
for file in ("index.html", "app.js", "perspective.mjs", "feed-config.json", "_headers"):
    if not (root / file).is_file():
        raise RuntimeError(f"Missing required file: {file}")
if "topic-writer-toggle" not in (root / "index.html").read_text(encoding="utf-8"):
    raise RuntimeError("Topic Writer missing")
if not data["news"] and not data["india_news"]:
    raise RuntimeError("No news returned: refusing an empty preview")
print("PREVIEW bundle validated. Private editorial issues intentionally excluded.")
PY
