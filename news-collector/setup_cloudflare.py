"""Cloudflare Worker bootstrap with narrow namespace ownership and no secret logs.

Supported commands:
  provision: reuse or create exactly one dedicated KV namespace, then
             generate an ephemeral Wrangler config from the reviewed template
  discover:  verify a deployed public Worker health endpoint and emit its URL
Both commands fail closed; they never touch unrelated Cloudflare resources.
"""
import json
import os
import re
import sys
import time
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

ROOT = Path(__file__).resolve().parents[1]
ACCOUNT = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "")
TOKEN = os.environ.get("CLOUDFLARE_API_TOKEN", "")
API = "https://api.cloudflare.com/client/v4"
NAMESPACE_NAME = "signaldesk-news-shared-cache"
SCRIPT_NAME = "signaldesk-news-feed"


def api(method, path, payload=None):
    if not re.fullmatch(r"[0-9a-f]{32}", ACCOUNT):
        raise RuntimeError("Cloudflare account identifier is missing or invalid")
    if not TOKEN:
        raise RuntimeError("Cloudflare API token is not configured")
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = Request(API + "/accounts/" + ACCOUNT + path, data=data, method=method,
                  headers={"Authorization": "Bearer " + TOKEN,
                           "Content-Type": "application/json"})
    try:
        with urlopen(req, timeout=20) as resp:
            answer = json.load(resp)
    except HTTPError as exc:
        raise RuntimeError(f"Cloudflare API permission or request denied (HTTP {exc.code}); "
                           "existing resources left untouched") from None
    except (URLError, ValueError):
        raise RuntimeError("Cloudflare API unavailable; no changes made") from None
    if answer.get("success") is not True:
        raise RuntimeError("Cloudflare API did not confirm success")
    return answer.get("result")


def output(name, value):
    target = os.environ.get("GITHUB_OUTPUT")
    if target:
        with open(target, "a", encoding="utf-8") as dest:
            dest.write(name + "=" + value + "\n")


def provision():
    found = []
    for page in range(1, 11):
        batch = api("GET", f"/storage/kv/namespaces?page={page}&per_page=100")
        if not isinstance(batch, list):
            raise RuntimeError("Unexpected KV namespace listing")
        found.extend(row for row in batch if row.get("title") == NAMESPACE_NAME)
        if len(batch) < 100:
            break
    else:
        raise RuntimeError("KV listing too large to verify dedicated namespace")
    if len(found) > 1:
        raise RuntimeError("Ambiguous existing KV namespaces; no changes")
    if found:
        chosen = found[0]
        print("Reusing exact dedicated SignalDesk KV namespace")
    else:
        chosen = api("POST", "/storage/kv/namespaces", {"title": NAMESPACE_NAME})
        print("Created dedicated SignalDesk KV namespace; no other resources modified")
    namespace_id = chosen.get("id") if isinstance(chosen, dict) else None
    if not isinstance(namespace_id, str) or not re.fullmatch(r"[a-f0-9]{32}", namespace_id):
        raise RuntimeError("Invalid KV namespace identifier")
    template = (ROOT / "news-collector/wrangler.template.jsonc").read_text("utf-8")
    if template.count("__SIGNALDESK_KV_NAMESPACE_ID__") != 1:
        raise RuntimeError("Unrecognized Worker configuration template")
    generated = template.replace("__SIGNALDESK_KV_NAMESPACE_ID__", namespace_id)
    filename = ROOT / "news-collector/wrangler.generated.jsonc"
    filename.write_text(generated, encoding="utf-8")
    output("kv_ready", "true")
    print("Generated Wrangler config for cron */15; no model or X secrets")


def discover():
    # This API requires Workers Scripts Read/Write. A Pages-only token cannot
    # reveal a Workers account subdomain, and we do not guess it.
    result = api("GET", "/workers/subdomain")
    subdomain = result.get("subdomain") if isinstance(result, dict) else None
    if not isinstance(subdomain, str) or not re.fullmatch(r"[a-z0-9-]{1,63}", subdomain):
        raise RuntimeError("Worker account subdomain is unavailable")
    url = "https://" + SCRIPT_NAME + "." + subdomain + ".workers.dev"
    # Verify the setting of exactly this Worker. Wrangler can deploy a script
    # successfully while its workers.dev public route remains disabled.
    setting = api("GET", "/workers/scripts/" + SCRIPT_NAME + "/subdomain")
    if not isinstance(setting, dict) or type(setting.get("enabled")) is not bool:
        raise RuntimeError("Unable to validate Worker-specific workers.dev routing")
    print("Worker-specific workers.dev routing enabled:", setting["enabled"])
    if setting["enabled"] is False:
        # This does NOT alter Cloudflare Access policies, other scripts, DNS,
        # the account subdomain, or previews. Only the intended public feed.
        changed = api("POST", "/workers/scripts/" + SCRIPT_NAME + "/subdomain",
                      {"enabled": True, "previews_enabled": False})
        if not isinstance(changed, dict) or changed.get("enabled") is not True:
            raise RuntimeError("Could not enable this Worker's specific public route")
        print("Enabled only SignalDesk feed worker's public production route")
    # A new workers.dev route can require propagation after Wrangler succeeds.
    # Do not print response bodies (which may be upstream HTML); report only
    # HTTP status or transport category. This is an exact endpoint probe.
    last_error = "not yet available"
    for attempt in range(1, 9):
        try:
            # Match our confirmed successful read-only diagnostic request.
            # Generic urllib defaults can receive a Cloudflare 403 before
            # reaching the Worker, even with the public route enabled.
            request = Request(url + "/health", headers={
                "User-Agent": "SignalDesk-ReadOnly-HealthDiagnostic/1.0",
                "Accept": "application/json",
            })
            with urlopen(request, timeout=12) as response:
                health = json.load(response)
            if (health.get("status") == "read_only" and
                    health.get("x_posting_enabled") is False and
                    health.get("ai_generation_enabled") is False):
                break
            last_error = "unexpected health response"
        except HTTPError as exc:
            last_error = "HTTP " + str(exc.code)
        except (URLError, ValueError):
            last_error = "endpoint not yet reachable"
        print(f"Collector health probe {attempt}/8: {last_error}")
        if attempt < 8:
            time.sleep(6)
    else:
        raise RuntimeError("Collector health failed despite Worker-specific route enabled: " + last_error + "; review Cloudflare Access for this hostname")
    output("live_feed_url", url + "/feed")
    print("Verified read-only collector health at " + url)
    return url + "/feed"


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "provision":
        provision()
    elif cmd == "discover":
        discover()
    else:
        raise SystemExit("Usage: setup_cloudflare.py provision|discover")


if __name__ == "__main__":
    main()
