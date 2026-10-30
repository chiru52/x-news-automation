"""Configure exactly the previously verified read-only public SignalDesk feed.

Never infer Worker hostnames from runtime GitHub token availability.
The endpoint is fixed and public; browser falls back to daily static snapshot
when /feed is empty, stale, blocked, malformed, or unavailable.
"""
import json
from pathlib import Path

APPROVED_ENDPOINT = "https://signaldesk-news-feed.littlekingchess.workers.dev/feed"
APPROVED_ORIGIN = "https://signaldesk-news-feed.littlekingchess.workers.dev"


def configure(output_dir):
    dest = Path(output_dir)
    config_path = dest / "feed-config.json"
    headers_path = dest / "_headers"
    result = {"schema_version": 1, "live_feed_url": None}
    try:
        current = json.loads(config_path.read_text(encoding="utf-8"))
        # Only the exact hostname and path verified through the owner's
        # GitHub read-only diagnostics are allowed. No network call needed.
        if (type(current) is not dict or current.get("schema_version") != 1 or
                current.get("live_feed_url") != APPROVED_ENDPOINT):
            raise ValueError("No approved public collector endpoint configured")
        original = headers_path.read_text(encoding="utf-8")
        if "connect-src 'self';" not in original:
            raise ValueError("Unexpected baseline Content Security Policy")
        updated = original.replace(
            "connect-src 'self';",
            "connect-src 'self' " + APPROVED_ORIGIN + ";"
        )
        headers_path.write_text(updated, encoding="utf-8")
        result["live_feed_url"] = APPROVED_ENDPOINT
        print("Exact public collector URL configured; browser keeps static fallback")
    except (OSError, ValueError, TypeError) as exc:
        print("Public collector configuration disabled; static feed retained (" +
              type(exc).__name__ + ")")
    config_path.write_text(json.dumps(result, separators=(",", ":")), encoding="utf-8")
    return result


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python -m news_collector.configure_live dist/signaldesk")
    configure(sys.argv[1])
