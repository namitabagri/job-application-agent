"""Deterministic ATS-style resume scoring (no LLM involved).

IMPORTANT: this is a transparent *proxy* for how Applicant Tracking Systems rank
resumes: keyword coverage against the job description + parse-friendliness checks.
Real systems (Workday, Greenhouse, Lever...) differ, so treat it as a guide.
"""
from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List

KEYWORD_WEIGHT = 0.85
STRUCTURE_WEIGHT = 0.15
REQUIRED_MULTIPLIER = 2     # required skills count double

_SECTION_ALIASES = {
    "summary": ("summary", "profile", "objective"),
    "skills": ("skills", "technical skills", "core skills"),
    "experience": ("experience", "work experience", "employment", "professional experience"),
    "education": ("education",),
}


def _pattern(keyword: str) -> re.Pattern:
    """Case-insensitive whole-term regex; spaces/hyphens interchangeable; optional plural."""
    tokens = [re.escape(t) for t in re.split(r"[\s\-]+", keyword.strip().lower()) if t]
    body = r"[\s\-]+".join(tokens)
    plural = "s?" if keyword.strip()[-1:].isalnum() else ""
    tail = r"(?![a-z0-9+#])" if keyword.strip()[-1:].isalnum() else r"(?![a-z0-9])"
    return re.compile(rf"(?<![a-z0-9]){body}{plural}{tail}", re.I)


def contains_keyword(text: str, keyword: str) -> bool:
    if not keyword or not keyword.strip():
        return False
    return bool(_pattern(keyword).search(text))


def _dedupe(items: Iterable[Any]) -> List[str]:
    seen, out = set(), []
    for it in items:
        s = str(it).strip()
        if s and s.lower() not in seen:
            seen.add(s.lower())
            out.append(s)
    return out


def jd_keywords(analysis: Dict[str, Any]) -> Dict[str, List[str]]:
    required = _dedupe(analysis.get("required_skills", []))
    req_lower = {r.lower() for r in required}
    other = [
        k for k in _dedupe(list(analysis.get("nice_to_have_skills", [])) + list(analysis.get("ats_keywords", [])))
        if k.lower() not in req_lower
    ]
    return {"required": required, "other": other}


def structure_checks(resume_text: str) -> Dict[str, bool]:
    headings = [h.strip("# ").strip().lower() for h in resume_text.splitlines() if h.lstrip().startswith("#")]
    checks = {
        f"has_{name}_section": any(any(a in h for a in aliases) for h in headings)
        for name, aliases in _SECTION_ALIASES.items()
    }
    checks["has_email"] = bool(re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", resume_text))
    checks["no_tables"] = not any(line.count("|") >= 2 and line.strip().startswith("|") for line in resume_text.splitlines())
    checks["no_emoji_or_icons"] = not re.search(r"[\U0001F300-\U0001FAFF\u2600-\u27BF]", resume_text)
    words = len(resume_text.split())
    checks["length_250_to_1000_words"] = 250 <= words <= 1000
    return checks


def score_resume(resume_text: str, analysis: Dict[str, Any]) -> Dict[str, Any]:
    """Score `resume_text` against a JD analysis dict. Returns a result dict (score 0-100)."""
    kws = jd_keywords(analysis)
    matched_req = [k for k in kws["required"] if contains_keyword(resume_text, k)]
    missing_req = [k for k in kws["required"] if k not in matched_req]
    matched_other = [k for k in kws["other"] if contains_keyword(resume_text, k)]
    missing_other = [k for k in kws["other"] if k not in matched_other]

    total_w = REQUIRED_MULTIPLIER * len(kws["required"]) + len(kws["other"])
    got_w = REQUIRED_MULTIPLIER * len(matched_req) + len(matched_other)
    keyword_score = got_w / total_w if total_w else 0.0

    checks = structure_checks(resume_text)
    structure_score = sum(checks.values()) / len(checks)

    total = round(100 * (KEYWORD_WEIGHT * keyword_score + STRUCTURE_WEIGHT * structure_score))
    return {
        "score": total,
        "keyword_score": round(100 * keyword_score),
        "structure_score": round(100 * structure_score),
        "matched_required": matched_req,
        "missing_required": missing_req,
        "matched_other": matched_other,
        "missing_other": missing_other,
        "checks": checks,
        "word_count": len(resume_text.split()),
    }
