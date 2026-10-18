"""Builds the deep agent: an orchestrator + four specialised sub-agents."""
from __future__ import annotations

from typing import Optional, Sequence

from deepagents import create_deep_agent
from langchain_openai import ChatOpenAI

from . import config, prompts
from .tools import ats_score_resume, fetch_job_description, internet_search


def _pick(tools: Sequence, *names: str) -> list:
    return [t for t in tools if getattr(t, "name", None) in names]


def build_subagents(web_tools: Sequence) -> list[dict]:
    """Each sub-agent has its own prompt + toolset => 'context quarantine'.
    Raw job-posting pages are read inside the analyst's context and never reach the orchestrator."""
    return [
        {
            "name": "job-search-agent",
            "description": "Finds real, current job postings; saves /jobs.json and returns a <JOBS> block.",
            "system_prompt": prompts.job_search_prompt(0),  # replaced in build_agent
            "tools": _pick(web_tools, "internet_search"),
        },
        {
            "name": "jd-analyst-agent",
            "description": "Fetches each job description and extracts required skills, "
                           "nice-to-haves and ATS keywords into /analysis/job_N.json.",
            "system_prompt": prompts.jd_analyst_prompt(),
            "tools": _pick(web_tools, "fetch_job_description", "internet_search"),
        },
        {
            "name": "project-advisor-agent",
            "description": f"Finds skill gaps and suggests at most {config.MAX_PROJECTS} portfolio "
                           "projects per job into /projects/job_N.json.",
            "system_prompt": prompts.project_advisor_prompt(),
            "tools": [],
        },
        {
            "name": "resume-writer-agent",
            "description": "Writes a tailored, ATS-optimised resume per job into /resumes/job_N.md "
                           "and iterates using the ATS scoring tool.",
            "system_prompt": prompts.resume_writer_prompt(),
            "tools": [ats_score_resume],
        },
    ]


def build_agent(model=None, n_jobs: int = config.DEFAULT_JOBS, web_tools: Optional[Sequence] = None):
    """Create the compiled LangGraph agent.

    Args:
        model: any LangChain chat model. Defaults to ChatOpenAI(OPENAI_MODEL).
        n_jobs: number of postings to process.
        web_tools: override [internet_search, fetch_job_description] (tests use stubs).
    """
    if model is None:
        model = ChatOpenAI(model=config.model_name(), temperature=0.2)
    web_tools = list(web_tools) if web_tools is not None else [internet_search, fetch_job_description]
    subagents = build_subagents(web_tools)
    subagents[0]["system_prompt"] = prompts.job_search_prompt(n_jobs)
    return create_deep_agent(
        model=model,
        tools=[],                              # orchestrator only delegates + manages files
        system_prompt=prompts.main_instructions(n_jobs),
        subagents=subagents,
    )
