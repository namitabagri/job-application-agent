# 🎯 Job Application Agent (LangChain Deep Agents)

Upload your resume, name a target role + location. For each of N live job postings the agent will:

1. **Identify the JD** - fetch the posting and summarise it
2. **Identify required skills** - required / nice-to-have / exact ATS keywords
3. **Suggest projects** - at most 2 per job, aimed at your skill gaps and the JD's responsibilities
4. **Write a tailored, ATS-optimised resume** - with those projects and the matching skills, then
   self-check it with an ATS scoring tool and revise until it reaches the target score

Based on the DataCamp tutorial https://www.datacamp.com/tutorial/deep-agents, extended with a
different workflow (analysis + projects + resume instead of cover letters).

## Architecture

```
 Streamlit UI (app.py)  /  CLI (cli.py)
      │ resume + title + location + skills (+ resume seeded into the virtual FS)
      ▼
 runner.run_job_agent() ───────────────────────────────────────────┐
      ▼                                                            │ build_reports():
┌───────────── DEEP AGENT: orchestrator (plan → delegate → verify) ┐│  parse files, score the
│ write_todos · task · ls · read_file                              ││  ORIGINAL vs TAILORED resume
│                                                                  ││  in Python (ats.py)
│ 1 job-search-agent     [internet_search]      → /jobs.json       ││
│ 2 jd-analyst-agent     [fetch_job_description,→ /analysis/job_N.json
│                         internet_search]                         ││
│ 3 project-advisor-agent [no web]              → /projects/job_N.json
│ 4 resume-writer-agent  [ats_score_resume] ⟲   → /resumes/job_N.md││
│        (write → score → revise, max 2x until score ≥ 85)         ││
│                                                                  ││
│   Shared virtual file system: /resume.txt (seeded) + all above   ││
└──────────────────────────────────────────────────────────────────┘│
      ▼                                                             ▼
 final <JOBS> block                                   exports.py → ZIP (.docx/.md resumes, report, CSV)
```

## Concepts → code

| Deep-agent concept | Where |
|---|---|
| Detailed system prompts | `src/jobagent/prompts.py` (workflow, schemas, truthfulness + ATS rules) |
| Planning tool | built-in `write_todos` |
| Sub-agents / context quarantine | `agent.py::build_subagents` - raw JD pages stay inside the analyst's context |
| Virtual file system as shared memory | files written by one sub-agent are read by the next; `/resume.txt` is seeded in `runner.py` |
| Custom tools | `tools.py`: search, JD fetch, and `ats_score_resume` (reads file state via `ToolRuntime`) |
| Agent loop with feedback | resume-writer: write → `ats_score_resume` → revise |
| Deterministic scoring outside the LLM | `ats.py` (before/after scores shown in the UI are computed in Python) |

## File structure

```
app.py  cli.py  requirements.txt  .env.example
src/jobagent/  config · prompts · tools · agent · runner · parsing · ats · documents · exports
tests/         ats · parsing · exports+UI · end-to-end agent wiring (fake LLM)
sample_data/   sample_resume.txt
sample_output/ illustrative analysis / projects / tailored resume / ATS score
```

## Setup & run

```bash
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                  # add OPENAI_API_KEY and TAVILY_API_KEY
pytest -q                                             # 16 offline tests, no API keys needed
streamlit run app.py                                  # UI
python cli.py --resume sample_data/sample_resume.txt --jobs 3   # headless -> ./outputs/
```

A run takes roughly 3-8 minutes for 3 jobs (several searches, page fetches and 4 sub-agents).
Use the sidebar slider (1-5 jobs) to trade speed for coverage.

## How the ATS score works (read this)

`ats.py` is a transparent **proxy**, not a real ATS: 85% keyword coverage (required skills weigh
2x, matching is whole-term, case-insensitive, hyphen/plural tolerant) + 15% parse-friendliness
(standard sections, email, no tables, no emoji, 250-1000 words). Real systems differ; the biggest
real-world wins are the same though: exact JD wording, standard headings, single column, real text.

## Integrity guardrails

- The writer may only reword/reorder **real** experience; employers, dates, degrees and numbers are kept.
- Skills you lack never appear in Skills/Experience - only inside the *suggested projects*.
- Project bullets use `[X%]`-style placeholders; the app warns until you fill in real results.
- **Suggested projects are plans.** Build them before applying, and only claim what you can discuss
  in an interview. A resume that overstates skills can cost you the offer.

## Troubleshooting

| Problem | Fix |
|---|---|
| "No jobs could be parsed" | Open *Debug: raw agent output*; try `OPENAI_MODEL=gpt-4o` |
| JD analysis says `search_snippet` | The page blocked extraction; the agent fell back to search text (less complete) |
| Score stays below 85 | Remaining keywords are ones you don't truthfully have - build a project for them |
| Empty resume error | Scanned PDFs have no text layer - use a text PDF, DOCX or TXT |
| Run too slow / costly | Lower the number of jobs |
