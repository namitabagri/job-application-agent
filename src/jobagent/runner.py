"""Orchestration layer shared by the Streamlit app and the CLI."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List

from deepagents.backends.utils import create_file_data

from . import ats, config
from .agent import build_agent
from .parsing import (
    extract_jobs_from_text,
    get_file_content,
    get_json_file,
    message_text,
    normalize_jobs,
)


@dataclass
class JobReport:
    job: Dict[str, Any]
    analysis: Dict[str, Any] = field(default_factory=dict)   # JD analysis (skills, keywords...)
    gaps: List[str] = field(default_factory=list)            # required skills missing from original resume
    projects: List[Dict[str, Any]] = field(default_factory=list)
    resume_md: str = ""
    ats_before: Dict[str, Any] = field(default_factory=dict)
    ats_after: Dict[str, Any] = field(default_factory=dict)

    @property
    def job_id(self) -> int:
        return self.job["job_id"]


@dataclass
class AgentResult:
    reports: List[JobReport] = field(default_factory=list)
    final_text: str = ""
    files: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)

    @property
    def jobs(self) -> List[Dict[str, Any]]:
        return [r.job for r in self.reports]


def make_task_prompt(resume_text: str, title: str, location: str, skills: str = "", n_jobs: int = 3) -> str:
    skills = (skills or "").strip()
    skill_line = f"Prioritize these skills: {skills}\n" if skills else ""
    return (
        f"Process {n_jobs} job postings.\n"
        f"Target title: {title}\n"
        f"Target location(s): {location}\n"
        f"{skill_line}\n"
        f"RESUME RAW TEXT (also saved at {config.RESUME_PATH}):\n{resume_text[:config.RESUME_CHAR_LIMIT]}"
    )


def build_reports(jobs: List[Dict[str, Any]], files: Dict[str, Any], resume_text: str) -> AgentResult:
    """Assemble per-job reports from the files the sub-agents wrote, and score them in Python."""
    result = AgentResult(files=files)
    for job in jobs:
        n = job["job_id"]
        analysis = get_json_file(files, config.analysis_path(n))
        proj = get_json_file(files, config.projects_path(n))
        resume_md = get_file_content(files, config.resume_path(n))
        rep = JobReport(job=job, resume_md=resume_md)

        if isinstance(analysis, dict):
            rep.analysis = analysis
            rep.ats_before = ats.score_resume(resume_text, analysis)
            rep.gaps = rep.ats_before["missing_required"]
            if resume_md:
                rep.ats_after = ats.score_resume(resume_md, analysis)
        else:
            result.warnings.append(f"Job {n} ({job['company']}): JD analysis missing or invalid.")

        if isinstance(proj, dict):
            rep.projects = [p for p in proj.get("projects", []) if isinstance(p, dict)][: config.MAX_PROJECTS]
        else:
            result.warnings.append(f"Job {n} ({job['company']}): project suggestions missing.")
        if not resume_md:
            result.warnings.append(f"Job {n} ({job['company']}): tailored resume missing.")
        result.reports.append(rep)
    return result


def run_job_agent(
    resume_text: str,
    title: str,
    location: str,
    skills: str = "",
    n_jobs: int = config.DEFAULT_JOBS,
    agent=None,
) -> AgentResult:
    """Run the full pipeline and return parsed per-job reports."""
    if not resume_text.strip():
        raise ValueError("Resume text is empty - could not read the uploaded file.")
    n_jobs = max(1, min(int(n_jobs), config.MAX_JOBS_LIMIT))

    agent = agent or build_agent(n_jobs=n_jobs)
    state = {
        "messages": [{"role": "user", "content": make_task_prompt(resume_text, title, location, skills, n_jobs)}],
        # seed the virtual file system so every sub-agent can read the original resume
        "files": {config.RESUME_PATH: create_file_data(resume_text[: config.RESUME_CHAR_LIMIT])},
    }
    raw = agent.invoke(state, config={"recursion_limit": config.RECURSION_LIMIT})

    messages = raw.get("messages", [])
    final_text = message_text(messages[-1].content) if messages else ""
    files = raw.get("files", {}) or {}

    jobs = normalize_jobs(extract_jobs_from_text(final_text), limit=n_jobs)
    if not jobs:  # fallback: the search sub-agent also saved /jobs.json
        saved = get_json_file(files, config.JOBS_PATH)
        jobs = normalize_jobs(saved if isinstance(saved, list) else [], limit=n_jobs)

    result = build_reports(jobs, files, resume_text)
    result.final_text = final_text
    if not jobs:
        result.warnings.append("No jobs could be parsed from the agent's answer (see raw output).")
    for r in result.reports:
        if re.search(r"\[[^\]\n]{1,24}\]", r.resume_md.replace("](", "")):
            result.warnings.append(
                f"Job {r.job_id}: resume contains [placeholders] - fill in real metrics after building the projects."
            )
    return result
