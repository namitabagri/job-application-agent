"""End-to-end test of the deep-agent wiring WITHOUT real API calls.

One scripted fake LLM plays the orchestrator and all four sub-agents in sequence. It verifies:
planning -> delegation -> web tools -> shared virtual files (seeded resume visible to
sub-agents, files from one sub-agent readable by the next) -> real ATS tool reading file
state -> parsing -> per-job reports with before/after scores."""
import json

from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from langchain_core.tools import tool

from jobagent.agent import build_agent
from jobagent.runner import run_job_agent

RESUME = "Jane Doe\njane@example.com\nSkills: Python, PyTorch, RAG\nSenior ML Engineer at Acme 2020-2024"

JOBS = [
    {"job_id": 1, "company": "Acme AI", "title": "Senior ML Engineer", "location": "Remote",
     "link": "https://jobs.acme.ai/1", "why_fit": "PyTorch match"},
    {"job_id": 2, "company": "Beta Labs", "title": "LLM Engineer", "location": "Bangalore",
     "link": "https://beta.io/careers/2", "why_fit": "RAG experience"},
]
JOBS_BLOCK = f"<JOBS>\n{json.dumps(JOBS)}\n</JOBS>"


def analysis(n):
    return json.dumps({
        "job_id": n, "company": JOBS[n - 1]["company"], "title": JOBS[n - 1]["title"], "jd_source": "fetched",
        "jd_summary": "Build LLM systems.", "responsibilities": ["Ship models"],
        "required_skills": ["Python", "PyTorch", "Kubernetes"], "nice_to_have_skills": ["vLLM"],
        "ats_keywords": ["RAG", "CI/CD"],
    })


def projects(n):
    return json.dumps({"job_id": n, "skill_gaps": ["Kubernetes"], "projects": [
        {"name": f"P{n}a", "description": "d", "skills_demonstrated": ["Kubernetes"], "gaps_closed": ["Kubernetes"],
         "deliverables": ["repo"], "estimated_effort": "1 week", "resume_bullets": ["Deployed on Kubernetes [X%]"]},
        {"name": f"P{n}b", "description": "d", "skills_demonstrated": ["vLLM"], "gaps_closed": [],
         "deliverables": ["repo"], "estimated_effort": "1 week", "resume_bullets": ["Served vLLM"]},
        {"name": "TOO MANY", "description": "should be trimmed"},
    ]})


TAILORED = ("# Jane Doe\njane@example.com\n## Professional Summary\nML engineer.\n## Skills\n"
            "Python, PyTorch, RAG, Kubernetes, vLLM, CI/CD\n## Work Experience\n- Built ML systems.\n"
            "## Projects\n- Deployed on Kubernetes [X%]\n## Education\nB.Tech\n")


class FakeToolModel(GenericFakeChatModel):
    def bind_tools(self, tools, **kwargs):
        return self


def call(name, args, i):
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": f"c{i}"}])


@tool
def internet_search(query: str) -> str:
    """Fake search."""
    return json.dumps(JOBS)


@tool
def fetch_job_description(url: str) -> str:
    """Fake JD fetch."""
    return "Job description text. " * 30


def test_full_pipeline_with_fake_llm():
    s = [
        call("write_todos", {"todos": [{"content": "search", "status": "in_progress"}]}, 1),
        # --- search
        call("task", {"description": "find jobs", "subagent_type": "job-search-agent"}, 2),
        call("internet_search", {"query": "ml engineer"}, 3),
        call("write_file", {"file_path": "/jobs.json", "content": json.dumps(JOBS)}, 4),
        AIMessage(content=JOBS_BLOCK),
        # --- JD analysis (reads the SEEDED resume)
        call("task", {"description": "analyse", "subagent_type": "jd-analyst-agent"}, 5),
        call("read_file", {"file_path": "/resume.txt"}, 6),
        call("fetch_job_description", {"url": JOBS[0]["link"]}, 7),
        call("write_file", {"file_path": "/analysis/job_1.json", "content": analysis(1)}, 8),
        call("fetch_job_description", {"url": JOBS[1]["link"]}, 9),
        call("write_file", {"file_path": "/analysis/job_2.json", "content": analysis(2)}, 10),
        AIMessage(content="analysis saved"),
        # --- projects (reads files written by the previous sub-agent)
        call("task", {"description": "projects", "subagent_type": "project-advisor-agent"}, 11),
        call("read_file", {"file_path": "/analysis/job_1.json"}, 12),
        call("write_file", {"file_path": "/projects/job_1.json", "content": projects(1)}, 13),
        call("write_file", {"file_path": "/projects/job_2.json", "content": projects(2)}, 14),
        AIMessage(content="projects saved"),
        # --- resumes + ATS tool
        call("task", {"description": "resumes", "subagent_type": "resume-writer-agent"}, 15),
        call("write_file", {"file_path": "/resumes/job_1.md", "content": TAILORED}, 16),
        call("ats_score_resume", {"job_id": 1}, 17),
        call("write_file", {"file_path": "/resumes/job_2.md", "content": TAILORED}, 18),
        AIMessage(content="job_1: ok"),
        # --- verify + finish
        call("ls", {"path": "/resumes"}, 19),
        AIMessage(content=f"Done.\n{JOBS_BLOCK}"),
    ]
    agent = build_agent(model=FakeToolModel(messages=iter(s)), n_jobs=2,
                        web_tools=[internet_search, fetch_job_description])

    result = run_job_agent(RESUME, "ML Engineer", "Remote", n_jobs=2, agent=agent)

    assert [r.job["company"] for r in result.reports] == ["Acme AI", "Beta Labs"]
    r1 = result.reports[0]
    assert r1.analysis["required_skills"] == ["Python", "PyTorch", "Kubernetes"]
    assert r1.gaps == ["Kubernetes"]                       # computed in Python from the ORIGINAL resume
    assert len(r1.projects) == 2                           # third project trimmed (max 2)
    assert r1.ats_after["score"] > r1.ats_before["score"]  # tailoring improved the proxy score
    assert "## Projects" in r1.resume_md
    assert any("placeholders" in w for w in result.warnings)
    assert not any("missing" in w for w in result.warnings)
