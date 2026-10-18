"""Download helpers: per-job analysis report and a ZIP of everything."""
from __future__ import annotations

import io
import re
import zipfile

import pandas as pd

from .documents import md_to_docx
from .runner import AgentResult, JobReport


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-") or "job"


def report_markdown(rep: JobReport) -> str:
    a, j = rep.analysis, rep.job
    lines = [f"## {rep.job_id}. {j['company']} - {j['title']}", f"{j['location']} | {j['link']}", ""]
    if rep.ats_before and rep.ats_after:
        lines += [f"**ATS score (proxy):** original resume {rep.ats_before['score']} -> tailored {rep.ats_after['score']}", ""]
    if a:
        lines += ["### Job description summary", a.get("jd_summary", ""), ""]
        lines += ["### Required skills", ", ".join(a.get("required_skills", [])), ""]
        if a.get("nice_to_have_skills"):
            lines += ["### Nice-to-have skills", ", ".join(a["nice_to_have_skills"]), ""]
    if rep.gaps:
        lines += ["### Skill gaps in your original resume", ", ".join(rep.gaps), ""]
    if rep.projects:
        lines += ["### Suggested projects"]
        for i, p in enumerate(rep.projects, 1):
            lines += [
                f"**{i}. {p.get('name', 'Project')}** ({p.get('estimated_effort', '')})",
                p.get("description", ""),
                "- Skills: " + ", ".join(p.get("skills_demonstrated", [])),
                "- Deliverables: " + "; ".join(p.get("deliverables", [])),
                "",
            ]
    return "\n".join(lines)


def report_all_markdown(result: AgentResult) -> str:
    head = ["# Job Application Pack", "",
            "> Suggested projects are PLANS. Build them before adding them to a real application, "
            "and replace any [placeholders] with your actual results.", ""]
    return "\n".join(head + [report_markdown(r) + "\n---\n" for r in result.reports])


def jobs_dataframe(result: AgentResult) -> pd.DataFrame:
    rows = []
    for r in result.reports:
        rows.append({
            "Job": r.job_id, "Company": r.job["company"], "Title": r.job["title"],
            "Location": r.job["location"], "Apply": r.job["link"],
            "ATS before": r.ats_before.get("score"), "ATS after": r.ats_after.get("score"),
            "Skill gaps": ", ".join(r.gaps),
        })
    return pd.DataFrame(rows)


def build_zip(result: AgentResult) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("job_application_pack.md", report_all_markdown(result))
        z.writestr("jobs.csv", jobs_dataframe(result).to_csv(index=False))
        for r in result.reports:
            if r.resume_md:
                name = f"resumes/{r.job_id}_{_slug(r.job['company'])}"
                z.writestr(name + ".md", r.resume_md)
                z.writestr(name + ".docx", md_to_docx(r.resume_md))
    return buf.getvalue()
