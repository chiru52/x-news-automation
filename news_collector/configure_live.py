"""Opt-in static-site wiring for an already verified Cloudflare collector.

If the Worker is absent or the token lacks Workers-read permissions, this is
a no-op and the existing daily static feed remains functional. Never guess
account subdomains, never put a Cloudflare API token in public assets.
"""
import json
from pathlib import Path
from urllib.parse import urlparse
from runpy import run_path


def discover():
    script = Path(__file__).resolve().parents[1] / 'news-collector/setup_cloudflare.py'
    return run_path(str(script))['discover']()

def configure(output_dir):
    dest = Path(output_dir)
    config_path = dest / "feed-config.json"
    headers_path = dest / "_headers"
    baseline = {"schema_version": 1, "live_feed_url": None}
    try:
        endpoint = discover()
        parsed = urlparse(endpoint)
        if (parsed.scheme != "https" or parsed.path != "/feed" or parsed.query or
                not parsed.hostname.startswith("signaldesk-news-feed.") or
                not parsed.hostname.endswith(".workers.dev")):
            raise ValueError("Unexpected collector hostname")
        original = headers_path.read_text(encoding="utf-8")
        if "connect-src 'self';" not in original:
            raise ValueError("Unexpected CSP baseline")
        updated = original.replace("connect-src 'self';",
                                   "connect-src 'self' " + parsed.scheme + "://" + parsed.netloc + ";")
        headers_path.write_text(updated, encoding="utf-8")
        baseline["live_feed_url"] = endpoint
        print("Collector endpoint verified and added to public CSP allowlist")
    except (OSError, ValueError, RuntimeError) as exc:
        # A misconfigured optional shared collector must not break the static
        # daily site or any manual-copy workflow.
        print("Shared collector not connected; daily static feed retained (" + type(exc).__name__ + ")")
    config_path.write_text(json.dumps(baseline, separators=(",", ":")), encoding="utf-8")
    return baseline

if __name__ == "__main__":
    import sys
    if len(sys.argv)!=2:
        raise SystemExit("Usage: python -m news_collector.configure_live dist/signaldesk")
    configure(sys.argv[1])
