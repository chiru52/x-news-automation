"""Fail-closed, GET-only SignalDesk production release preflight.

For a human operator to review BEFORE a separately approved deployment.
Does not read credentials, invoke Wrangler, change Cloudflare, or publish to X.
"""
from __future__ import annotations

from scripts.check_live_news_worker import run, preview_deployment_report

EXPECTED = (
    "Production health origin",
    "Preview health origin",
    "Untrusted origin rejected",
    "Preview live feed",
    "Preview 7-day archive",
)


def evaluate_readiness(observations: list[dict]) -> dict:
    """Evaluate the existing bounded public read-only probe, not git CI status."""
    if not isinstance(observations, list):
        return {"ready": False, "blockers": list(EXPECTED)}
    by_label = {row.get("label"): row for row in observations if isinstance(row, dict)}
    blockers = []
    for label in EXPECTED:
        row = by_label.get(label)
        if not row or row.get("http_status") != 200 or row.get("cors") != "PASS":
            blockers.append(label)
            continue
        details = row.get("details", "")
        if label.endswith("health origin") or label == "Untrusted origin rejected":
            if details != "Read-only collector contract verified":
                blockers.append(label)
        elif label == "Preview live feed" and not details.startswith("Feed PASS: "):
            blockers.append(label)
    if len(observations) != len(EXPECTED):
        blockers.append("Unexpected number of checks")
    return {"ready": not blockers, "blockers": blockers}


def main() -> int:
    observations = run()
    preview = preview_deployment_report()
    readiness = evaluate_readiness(observations)
    print("\n# SignalDesk independent deployment preflight (GET-only)")
    print("Status: " + ("PASS" if readiness["ready"] else "BLOCKED"))
    print("Public static preview Global: " + str(preview["static_global_stories"]))
    print("Public static preview India: " + str(preview["static_india_stories"]))
    print("Public static preview image-bearing stories: " +
          str(preview["static_stories_with_images"]))
    if readiness["blockers"]:
        print("Failing checks: " + ", ".join(readiness["blockers"]))
    if not readiness["ready"]:
        print("Do NOT deploy: resolve CORS, live-feed or safety issues first.")
        return 1
    if any(preview[k] is None for k in ("static_global_stories", "static_india_stories")):
        print("Do NOT deploy: public static-preview counts could not be read.")
        return 1
    print("Read-only checks passed. Human approval and Cloudflare configuration "
          "verification are STILL required before any production deployment.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
