"""Conservative, offline checks tying Copilot claims to publisher excerpt IDs.

This is NOT a fact-checker. It can only check literal quantities in the limited
(unverified and sometimes truncated) source excerpts already supplied to Copilot.
No network access, AI requests, X posting or repository modifications.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
import re

REF = re.compile(r"\[(P\d+)\]")
WEB_LINK = re.compile(r"https?://[^\s]+", re.I)
QUANTITY = re.compile(
    r"(?<![\w])(?:[$€£₹]\s*)?\d[\d,]*(?:\.\d+)?"
    r"(?:\s*(?:%|percent|thousand|million|billion|trillion|bn|k|m|b))?(?!\w)",
    re.I,
)
TERMS = re.compile(r"[A-Za-z][A-Za-z0-9'-]{3,}")
CLAIM_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z])|;\s*")
COMMON = frozenset((
    "about", "across", "after", "along", "also", "among", "around", "being",
    "company", "companies", "could", "from", "have", "into", "more", "over",
    "plans", "reported", "reportedly", "says", "said", "that", "their",
    "there", "they", "this", "were", "what", "when", "which", "while",
    "will", "with", "would", "article", "news", "source", "claim", "first",
    "only", "than",
))
MULTIPLIERS = {
    "k": 1000, "thousand": 1000, "m": 1000000, "million": 1000000,
    "b": 1000000000, "bn": 1000000000, "billion": 1000000000,
    "trillion": 1000000000000,
}


def quantities(value: str) -> set[str]:
    """Normalize quantities for literal comparison (60K == 60,000).

    Numeric equivalence is not factual equivalence: units, eligibility,
    geography and meaning still require manual review.
    """
    output = set()
    text = WEB_LINK.sub("", REF.sub("", value or ""))
    for match in QUANTITY.finditer(text):
        value = match.group().strip()
        number = re.match(r"[$€£₹]?\s*(\d[\d,]*(?:\.\d+)?)", value)
        if not number:
            continue
        try:
            n = Decimal(number.group(1).replace(",", ""))
        except InvalidOperation:
            continue
        unit = value[number.end():].strip().lower()
        is_percent = unit in ("%", "percent")
        if unit in MULTIPLIERS:
            n *= MULTIPLIERS[unit]
        normalized = format(n.normalize(), "f")
        if "." in normalized:
            normalized = normalized.rstrip("0").rstrip(".")
        output.add(normalized + ("%" if is_percent else ""))
    return output


def claim_units(model_fields: dict) -> list[dict]:
    """Associate each explicit claim sentence with its own paragraph citations."""
    result = []
    for section in ("EVIDENCE", "WHY_IT_MATTERS"):
        body = str(model_fields.get(section) or "").strip()
        if not body or body.upper() in ("WITHHELD", "NONE"):
            continue
        for claim in CLAIM_SPLIT.split(body):
            claim = claim.strip()
            if not claim:
                continue
            ids = sorted(set(REF.findall(claim)), key=lambda i: int(i[1:]))
            result.append({"section": section, "text": claim, "refs": ids})
    return result[:16]


def audit_model_evidence(model_fields: dict, paragraphs: list[dict]) -> dict:
    """Report suspicious citation/quantity gaps; no semantic verification.

    Only numbers *inside the cited paragraph snippets* count as traceable.
    Since publisher text may be clipped at 550 chars, a flagged gap signals
    "check the original", not evidence of an incorrect factual statement.
    """
    by_id = {p["id"]: p["text"] for p in paragraphs}
    claims = claim_units(model_fields)
    flags = []
    for claim in claims:
        refs = [id_ for id_ in claim["refs"] if id_ in by_id]
        if not claim["refs"]:
            flags.append(f"{claim['section']} includes an uncited claim sentence")
            continue
        if not refs:
            # Unknown citation IDs are also handled by the original format check.
            flags.append(f"{claim['section']} cites no available publisher paragraph")
            continue
        claimed = quantities(claim["text"])
        cited = set().union(*(quantities(by_id[ref]) for ref in refs))
        for value in sorted(claimed - cited)[:3]:
            flags.append(f"{claim['section']} quantity {value} absent from cited excerpt(s) "
                         + ", ".join(refs))
    # Independently look for numeric details in the *public proposed copy*
    # which do not appear anywhere in referenced source snippets.
    draft = str(model_fields.get("DRAFT") or "")
    all_refs = {ref for c in claims for ref in c["refs"] if ref in by_id}
    supported = set().union(*(quantities(by_id[ref]) for ref in all_refs))
    for value in sorted(quantities(draft) - supported)[:3]:
        flags.append(f"DRAFT quantity {value} absent from cited publisher excerpt(s)")
    # Keep reports bounded, predictable and safe for a private review Issue.
    flags = list(dict.fromkeys(flags))[:8]
    return {
        "flags": flags,
        "claims": claims,
        "status": "needs_attention" if flags else "limited_precheck_only",
        "verified": False,
    }


def focused_excerpt(value: str, related_claims: list[str], max_chars: int = 190) -> str:
    """Choose the most claim-relevant window, not simply the paragraph prefix.

    Excerpts are deliberately short and may omit vital context; editor must
    open the full publisher article before trusting or publishing anything.
    """
    source = re.sub(r"\s+", " ", value).strip()
    if len(source) <= max_chars:
        return source
    terms = set()
    numbers = set()
    for claim in related_claims:
        terms.update(w.lower() for w in TERMS.findall(WEB_LINK.sub("", REF.sub("", claim)))
                     if w.lower() not in COMMON)
        numbers.update(quantities(claim))
    # Try windows near words or quantities in the raw paragraph. Scores prefer
    # literal numeric matches; keyword overlap chooses more useful context.
    starts = {0, max(0, len(source) - max_chars)}
    for token in terms:
        for m in list(re.finditer(r"(?<!\w)" + re.escape(token) + r"(?!\w)",
                                  source, re.I))[:6]:
            starts.add(max(0, m.start() - max_chars // 4))
    for m in list(QUANTITY.finditer(source))[:24]:
        if quantities(m.group()) & numbers:
            starts.add(max(0, m.start() - max_chars // 3))
    best = None
    for begin in sorted(starts):
        end = min(len(source), begin + max_chars)
        window = source[begin:end]
        overlap = len(terms & {w.lower() for w in TERMS.findall(window)})
        numeric = len(numbers & quantities(window))
        # Reward meaningful matches, prefer an earlier window for ties.
        score = (numeric * 12 + overlap * 2, -begin)
        if best is None or score > best[0]:
            best = (score, begin, end)
    _, begin, end = best
    if begin:
        # Avoid displaying a broken first word.
        space = source.find(" ", begin, min(begin + 25, end))
        if space >= 0:
            begin = space + 1
    if end < len(source):
        # Avoid a broken final word when feasible.
        space = source.rfind(" ", max(begin, end - 25), end)
        if space > begin:
            end = space
    excerpt = source[begin:end].strip(" ,;:")
    return ("…" if begin else "") + excerpt + ("…" if end < len(source) else "")
