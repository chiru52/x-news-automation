"""Fail-closed inventory of the exact SignalDesk Worker; Cloudflare GET ONLY.

Uses a separately permissioned read-only Cloudflare token when run in Actions.
Do not reuse the old provision/discover functions: they can write Cloudflare.
Never log API response bodies, secret values, binding IDs or account IDs.
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

SCRIPT = "signaldesk-news-feed"
BASE = "https://api.cloudflare.com/client/v4"
CRON = "*/15 * * * *"
UUID = re.compile(r"^[0-9a-fA-F]{8}-(?:[0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}$")
ACCOUNT = re.compile(r"^[0-9a-fA-F]{32}$")
ROUTES = {
    "settings": f"/workers/scripts/{SCRIPT}/settings",
    "schedules": f"/workers/scripts/{SCRIPT}/schedules",
    "deployments": f"/workers/scripts/{SCRIPT}/deployments",
    "subdomain": f"/workers/scripts/{SCRIPT}/subdomain",
}


def cloudflare_get(name, *, account_id, token):
    """One capped GET for one known script and one allowlisted API route."""
    if name not in ROUTES or not ACCOUNT.fullmatch(account_id or "") or not token:
        raise ValueError("Read-only Cloudflare configuration incomplete")
    request = urllib.request.Request(
        BASE + "/accounts/" + account_id + ROUTES[name],
        method="GET",
        headers={"Authorization": "Bearer " + token, "Accept": "application/json",
                 "User-Agent": "SignalDeskReadOnlyInventory/1.0"},
    )
    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            raw = response.read(150_001)
            if len(raw) > 150_000:
                raise ValueError("Read-only API response exceeded size limit")
            payload = json.loads(raw)
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError,
            UnicodeError, json.JSONDecodeError) as exc:
        # No raw errors, API payloads, response URLs or authentication headers.
        raise ValueError("Cloudflare read-only metadata endpoint unavailable") from None
    if not isinstance(payload, dict) or payload.get("success") is not True:
        raise ValueError("Cloudflare API did not confirm a successful read")
    return payload.get("result")


def evaluate_inventory(parts):
    """Pure metadata checks; return sanitized summary and rollback identifiers.

    This is an *inventory*, never a deployment authorization or safety approval.
    """
    blockers = []
    if not isinstance(parts, dict):
        parts = {}

    settings = parts.get("settings")
    bindings = settings.get("bindings") if isinstance(settings, dict) else None
    if not isinstance(bindings, list):
        blockers.append("Worker bindings cannot be verified")
        bindings = []
    live_cache = [binding for binding in bindings
                  if isinstance(binding, dict) and binding.get("name") == "NEWS_CACHE"]
    if len(live_cache) != 1 or live_cache[0].get("type") != "kv_namespace" or not (
        isinstance(live_cache[0].get("namespace_id"), str) and
        ACCOUNT.fullmatch(live_cache[0]["namespace_id"])
    ):
        blockers.append("Dedicated NEWS_CACHE KV binding missing or ambiguous")
    if len(bindings) != 1:
        blockers.append("Unexpected Worker bindings require human review")

    schedule = parts.get("schedules")
    schedules = schedule.get("schedules") if isinstance(schedule, dict) else None
    if not isinstance(schedules, list) or len(schedules) != 1 or not (
        isinstance(schedules[0], dict) and schedules[0].get("cron") == CRON
    ):
        blockers.append("Cron must be exactly one 15-minute schedule")

    public_route = parts.get("subdomain")
    if not isinstance(public_route, dict) or public_route.get("enabled") is not True:
        blockers.append("Exact SignalDesk workers.dev route not confirmed enabled")

    result = parts.get("deployments")
    deployments = result.get("deployments") if isinstance(result, dict) else None
    rollback = None
    if not isinstance(deployments, list) or not deployments:
        blockers.append("Existing Worker deployment/rollback version unavailable")
    else:
        # API ordering is not assumed. Validate and choose newest timestamp.
        ordered = sorted((d for d in deployments if isinstance(d, dict)),
                         key=lambda row: str(row.get("created_on", "")), reverse=True)
        if not ordered:
            blockers.append("Existing Worker deployment metadata invalid")
        else:
            selected = ordered[0]
            versions = selected.get("versions")
            if not UUID.fullmatch(str(selected.get("id", ""))) or not (
                isinstance(versions, list) and len(versions) == 1 and
                isinstance(versions[0], dict) and
                UUID.fullmatch(str(versions[0].get("version_id", ""))) and
                versions[0].get("percentage") == 100
            ):
                blockers.append("Cannot preserve single currently active rollback version")
            else:
                rollback = {
                    "previous_deployment_id": selected["id"],
                    "previous_version_id": versions[0]["version_id"],
                }

    return {
        "worker": SCRIPT,
        "inventory_pass": not blockers,
        "checks": {
            "kv_binding": not any("binding" in reason or "NEWS_CACHE" in reason for reason in blockers),
            "cron": not any("Cron" in reason for reason in blockers),
            "public_route": not any("route" in reason for reason in blockers),
            "rollback_version": rollback is not None,
        },
        "blockers": blockers,
        # The version UUID is NOT an API key; preserve it as a private
        # short-retention workflow artifact to support manual rollback review.
        "rollback_candidate": rollback,
        "production_change_authorized": False,
    }


def main() -> int:
    account = os.getenv("CLOUDFLARE_ACCOUNT_ID", "")
    token = os.getenv("SIGNALDESK_CLOUDFLARE_READ_TOKEN", "")
    if not ACCOUNT.fullmatch(account) or not token:
        print("BLOCKED: read-only Cloudflare account/token not configured.")
        print("Use a Workers Metadata Read-Only token; do not paste credentials into chat.")
        return 2
    parts = {}
    for name in ROUTES:
        try:
            parts[name] = cloudflare_get(name, account_id=account, token=token)
        except ValueError:
            print("BLOCKED: could not read exact SignalDesk " + name + " metadata.")
            return 2

    report = evaluate_inventory(parts)
    # Never write raw fetched metadata, bindings, account ID or auth token.
    destination = Path(os.getenv("SIGNALDESK_INVENTORY_ARTIFACT", "/tmp/signaldesk-worker-inventory.json"))
    destination.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("SignalDesk read-only Cloudflare inventory: " +
          ("PASS" if report["inventory_pass"] else "BLOCKED"))
    for check, passed in report["checks"].items():
        print("  " + check + ": " + ("PASS" if passed else "BLOCKED"))
    for problem in report["blockers"]:
        print("  Blocker: " + problem)
    print("No Worker, Pages, Cron, KV, route, or X writes were performed.")
    print("Rollback metadata saved to a private short-retention artifact. Deployment still requires separate approval.")
    return 0 if report["inventory_pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
