"""Custom tools. Each is a plain function decorated with @tool; the *docstring*
becomes the description the LLM sees, so write it for the model."""
from __future__ import annotations

import json
from typing import Any, Dict, Literal

from langchain.tools import ToolRuntime, tool

from . import ats, config
from .parsing import get_file_content, parse_json_text

JD_CHAR_LIMIT = 7000


@tool
def internet_search(
    query: str,
    max_results: int = 5,
    topic: Literal["general", "news", "finance"] = "general",
) -> Dict[str, Any]:
    """Search the web for current information, such as live job postings.

    Args:
        query: The search query, e.g. 'Senior ML Engineer Bangalore site:lever.co'.
        max_results: Number of results to return (1-10).
        topic: Search category. Use 'general' for job postings.

    Returns:
        Search results with titles, URLs and content snippets.
    """
    key = config.tavily_key()
    if not key:
        raise RuntimeError("TAVILY_API_KEY is not set.")
    from tavily import TavilyClient  # lazy: tests don't need the package configured

    return TavilyClient(api_key=key).search(
        query=query, max_results=max(1, min(int(max_results), 10)), topic=topic
    )


@tool
def fetch_job_description(url: str) -> str:
    """Fetch the full text of a job posting page so its requirements can be analysed.

    Args:
        url: The job posting URL (company careers page, Lever, Greenhouse, LinkedIn...).

    Returns:
        The page text (truncated), or a string starting with 'ERROR:' if it could not be read.
    """
    key = config.tavily_key()
    if not key:
        return "ERROR: TAVILY_API_KEY is not set."
    from tavily import TavilyClient

    try:
        res = TavilyClient(api_key=key).extract(urls=[url], format="text")
    except Exception as e:  # network / API failure
        return f"ERROR: could not fetch {url}: {e}"
    results = res.get("results") or []
    text = (results[0].get("raw_content") or "").strip() if results else ""
    if len(text) < 200:
        return f"ERROR: page returned little or no text for {url}. Use internet_search instead."
    return text[:JD_CHAR_LIMIT]


@tool
def ats_score_resume(job_id: int, runtime: ToolRuntime) -> str:
    """Score the tailored resume for a job against its job description (ATS proxy, 0-100).

    Reads /resumes/job_<job_id>.md and /analysis/job_<job_id>.json from the shared file
    system, so write the resume file FIRST. Returns the score, which required skills /
    keywords are still missing, and any failed formatting checks.

    Args:
        job_id: The job number (1-based).
    """
    files = runtime.state.get("files", {}) or {}
    resume_md = get_file_content(files, config.resume_path(job_id))
    analysis = parse_json_text(get_file_content(files, config.analysis_path(job_id)))
    if not resume_md:
        return f"ERROR: {config.resume_path(job_id)} not found. Write the resume first."
    if not isinstance(analysis, dict):
        return f"ERROR: {config.analysis_path(job_id)} missing or invalid JSON."
    r = ats.score_resume(resume_md, analysis)
    return json.dumps(
        {
            "score": r["score"],
            "target": config.ATS_TARGET,
            "missing_required_skills": r["missing_required"],
            "missing_other_keywords": r["missing_other"][:12],
            "failed_checks": [k for k, ok in r["checks"].items() if not ok],
            "word_count": r["word_count"],
            "advice": "Add missing keywords ONLY if they are truthful for the candidate "
                      "or demonstrated by a suggested project.",
        }
    )
