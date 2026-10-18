"""Turn raw agent output / virtual-file contents into clean Python data."""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from .config import DEFAULT_JOBS

_JOBS_RE = re.compile(
    r"<JOBS>\s*(?:```[\w-]*\s*)?(\[.*?\])\s*(?:```)?\s*</JOBS>", re.S | re.I
)
_FENCE_RE = re.compile(r"^\s*```[\w-]*\s*|\s*```\s*$")


def message_text(content: Any) -> str:
    """LLM message content can be a str or a list of content blocks."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
        return "\n".join(parts)
    return str(content or "")


def parse_json_text(raw: str) -> Any:
    """json.loads with small repairs for common LLM mistakes. Returns None on failure."""
    if not raw:
        return None
    raw = _FENCE_RE.sub("", raw.strip()).strip()
    no_trailing = re.sub(r",\s*([\]}])", r"\1", raw)
    for cand in (raw, no_trailing, re.sub(r"(?<!\\)'", '"', no_trailing)):
        try:
            return json.loads(cand)
        except Exception:
            continue
    return None


def extract_jobs_from_text(text: str) -> List[Dict[str, Any]]:
    """Pull the JSON array out of <JOBS>...</JOBS>. Returns [] if absent/invalid."""
    m = _JOBS_RE.search(text or "")
    obj = parse_json_text(m.group(1)) if m else None
    return obj if isinstance(obj, list) else []


def normalize_jobs(items: List[Dict[str, Any]], limit: int = DEFAULT_JOBS) -> List[Dict[str, Any]]:
    """Case-insensitive keys, required http link, de-duplicated, capped, numbered 1..N."""
    out: List[Dict[str, Any]] = []
    seen = set()
    for it in items:
        if not isinstance(it, dict):
            continue
        d = {str(k).strip().lower().replace(" ", "_"): v for k, v in it.items()}
        link = str(d.get("link") or d.get("url") or "").strip()
        if not link.lower().startswith(("http://", "https://")) or link in seen:
            continue
        seen.add(link)
        out.append(
            {
                "job_id": len(out) + 1,
                "company": str(d.get("company") or "—").strip() or "—",
                "title": str(d.get("title") or "—").strip() or "—",
                "location": str(d.get("location") or "—").strip() or "—",
                "link": link,
                "why_fit": str(d.get("why_fit") or d.get("good_match") or "—").strip() or "—",
            }
        )
    return out[:limit]


def get_file_content(files: Dict[str, Any], path: str) -> str:
    """Read a file from the agent's virtual file system, whatever the storage shape.

    deepagents versions store content as str, list[str] or {"content": ...},
    and keys may or may not have a leading slash.
    """
    if not files:
        return ""
    entry = files.get(path) or files.get(path.lstrip("/"))
    if entry is None:
        return ""
    if isinstance(entry, dict):
        entry = entry.get("content", "")
    if isinstance(entry, list):
        entry = "\n".join(str(x) for x in entry)
    return str(entry or "").strip()


def get_json_file(files: Dict[str, Any], path: str) -> Optional[Any]:
    return parse_json_text(get_file_content(files, path))
