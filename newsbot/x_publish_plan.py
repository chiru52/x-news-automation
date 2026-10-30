"""Stage 34: immutable per-draft, per-account X post approval planning.

PLANNING ONLY: no X API client, no credentials, no publishing, no GitHub writes.
Reviewed labels and plans do not constitute publication approval.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys

from .x_preflight import PreflightBlocked, github_json, validate_issue, REPO

HANDLE = re.compile(r"^[A-Za-z0-9_]{1,15}$")
SHA = re.compile(r"^[a-f0-9]{64}$")


def fingerprint(number: int, handle: str, text: str) -> str:
    """Bind the exact reviewed text, issue, repo, and intended account."""
    key = {"v": 1, "repository": REPO, "issue_number": number,
           "destination_handle": handle, "text": text}
    raw = json.dumps(key, ensure_ascii=False, sort_keys=True,
                     separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(b"X-NEWS-POST-PLAN-V1\n" + raw).hexdigest()


def make_plan(issue: dict, number: int, handle: str) -> dict:
    if not isinstance(handle, str) or not HANDLE.fullmatch(handle):
        raise PreflightBlocked("Destination X handle must have 1–15 letters, digits or underscores")
    preview = validate_issue(issue, number)
    normalized = handle.lower()
    # Bind the chosen handle, but require verified numeric X user ID before
    # any future send. Handles alone do not prove account identity.
    digest = fingerprint(number, normalized, preview["draft"])
    return {
        "issue_number": number, "issue_url": preview["url"],
        "destination_handle_unverified": normalized, "text": preview["draft"],
        "sha256": digest, "publication_authorized": False, "send_enabled": False
    }


def check_request(plan: dict, expected_sha256: str, confirmation: str,
                  durable_records: list[dict]) -> bool:
    """Offline prerequisite check only; NOT permission to send.

    Caller must separately verify X numeric account identity, prove an atomic
    durable reservation exists for the precise key, and obtain explicit human
    approval. This function has no network, persistence or publishing ability.
    """
    if (not isinstance(plan, dict) or plan.get("publication_authorized") is not False
            or plan.get("send_enabled") is not False):
        raise PreflightBlocked("Plan is not a non-publishing plan")
    sha = plan.get("sha256")
    number = plan.get("issue_number")
    handle = plan.get("destination_handle_unverified")
    if not isinstance(sha, str) or not SHA.fullmatch(sha):
        raise PreflightBlocked("Invalid plan digest")
    if (not isinstance(number, int) or isinstance(number, bool) or number < 1
            or not isinstance(handle, str) or not HANDLE.fullmatch(handle)
            or handle != handle.lower()):
        raise PreflightBlocked("Invalid plan identity")
    if not isinstance(plan.get("text"), str) or fingerprint(number, handle, plan["text"]) != sha:
        raise PreflightBlocked("Plan payload does not match its immutable fingerprint")
    if expected_sha256 != sha:
        raise PreflightBlocked("Draft changed or expected fingerprint mismatch")
    phrase = f"APPROVE X POST #{number} @{handle} {sha}"
    if confirmation != phrase:
        raise PreflightBlocked("Exact separate publication approval phrase not provided")
    if not isinstance(durable_records, list):
        raise PreflightBlocked("Durable posting history is unavailable")
    for record in durable_records:
        if not isinstance(record, dict):
            raise PreflightBlocked("Malformed durable posting history")
        state = record.get("state")
        if state not in ("reserved", "unknown", "sent", "aborted"):
            raise PreflightBlocked("Unexpected posting ledger state")
        # Fail closed for any prior record touching this issue/account OR
        # the immutable draft fingerprint, regardless of its state.
        if (record.get("sha256") == sha or
            (record.get("issue_number") == number and
             record.get("destination_handle") == handle)):
            raise PreflightBlocked("Duplicate or prior posting reservation exists")
    # True ONLY means the pure preliminary checks passed. A separate atomic,
    # durable send-reservation mechanism is still REQUIRED before any API call.
    return True


def render_plan(plan: dict) -> str:
    text = plan["text"]
    ticks = re.findall(r"\x60+", text)
    fence = chr(96) * max(4, 1 + max((len(x) for x in ticks), default=0))
    phrase = (f"APPROVE X POST #{plan['issue_number']} "
              f"@{plan['destination_handle_unverified']} {plan['sha256']}")
    return (
        "## Stage 34 — X publication approval planning ONLY\n\n"
        f"**Private reviewed draft:** [#{plan['issue_number']}]({plan['issue_url']})\n\n"
        f"**Intended X account (NOT authenticated):** @{plan['destination_handle_unverified']}\n\n"
        f"**Immutable SHA-256 fingerprint:** \`{plan['sha256']}\`\n\n"
        f"**Exact text snapshot:**\n\n{fence}text\n{text}\n{fence}\n\n"
        "**Future approval phrase (REFERENCE ONLY; entering it here does nothing):**\n\n"
        f"{fence}text\n{phrase}\n{fence}\n\n"
        "**NO POST SENT. Publishing remains DISABLED.** This run does not read "
        "X secrets, authenticate the intended account, reserve a delivery in "
        "durable storage, or grant publication permission. A separate future "
        "authorization, verified numeric X account identity, and atomic "
        "duplicate-post protection are mandatory before any X API call.\n"
    )


def main() -> int:
    try:
        raw = os.environ.get("ISSUE_NUMBER", "")
        handle = os.environ.get("DESTINATION_HANDLE", "")
        if not re.fullmatch(r"[1-9][0-9]{0,7}", raw):
            raise PreflightBlocked("Enter a positive private AI Draft Issue number")
        if os.environ.get("GITHUB_REPOSITORY") != REPO or not os.environ.get("GH_TOKEN"):
            raise PreflightBlocked("Read-only private GitHub access required")
        if not HANDLE.fullmatch(handle):
            raise PreflightBlocked("Enter a valid X username without @")
        repo = github_json(f"repos/{REPO}")
        if repo.get("private") is not True or repo.get("full_name") != REPO:
            raise PreflightBlocked("Editorial repository must remain private")
        issue = github_json(f"repos/{REPO}/issues/{int(raw)}")
        plan = make_plan(issue, int(raw), handle)
        target = os.environ.get("GITHUB_STEP_SUMMARY")
        if target:
            with open(target, "a", encoding="utf-8") as file:
                file.write(render_plan(plan))
        else:
            print("Publication plan created only; no X post sent.")
        return 0
    except (PreflightBlocked, OSError, json.JSONDecodeError) as error:
        safe = str(error) if isinstance(error, PreflightBlocked) else "Private read failed"
        print("Stage 34 plan blocked: " + safe, file=sys.stderr)
        return 1
    except Exception:
        # Never dump API responses, private Issue text, subprocess stderr or tokens.
        print("Stage 34 plan blocked: private GitHub read failed", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
