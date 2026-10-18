"""Central configuration: environment variables and constants."""
from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()  # reads .env if present

DEFAULT_MODEL = "gpt-4o-mini"
DEFAULT_JOBS = 3             # jobs processed per run (each job = JD + projects + resume)
MAX_JOBS_LIMIT = 5
MAX_PROJECTS = 2             # suggested projects per job
ATS_TARGET = 85              # resume-writer revises until it reaches this score
RESUME_CHAR_LIMIT = 8000     # truncate resume text sent to the LLM
RECURSION_LIMIT = 150        # safety cap on agent steps

# Paths inside the agent's *virtual* file system (shared by all sub-agents)
RESUME_PATH = "/resume.txt"      # seeded by us: the candidate's original resume
JOBS_PATH = "/jobs.json"         # written by job-search-agent
ANALYSIS_DIR = "/analysis"       # /analysis/job_N.json   (jd-analyst-agent)
PROJECTS_DIR = "/projects"       # /projects/job_N.json   (project-advisor-agent)
RESUMES_DIR = "/resumes"         # /resumes/job_N.md      (resume-writer-agent)


def analysis_path(n: int) -> str:
    return f"{ANALYSIS_DIR}/job_{n}.json"


def projects_path(n: int) -> str:
    return f"{PROJECTS_DIR}/job_{n}.json"


def resume_path(n: int) -> str:
    return f"{RESUMES_DIR}/job_{n}.md"


def openai_key() -> str:
    return os.environ.get("OPENAI_API_KEY", "").strip()


def tavily_key() -> str:
    return os.environ.get("TAVILY_API_KEY", "").strip()


def model_name() -> str:
    return os.environ.get("OPENAI_MODEL", DEFAULT_MODEL)


def missing_keys() -> list[str]:
    """Names of required API keys that are not set."""
    missing = []
    if not openai_key():
        missing.append("OPENAI_API_KEY")
    if not tavily_key():
        missing.append("TAVILY_API_KEY")
    return missing
