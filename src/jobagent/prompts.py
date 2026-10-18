"""All prompts live here. Deep agents depend heavily on detailed prompts,
so keeping them in one file makes them easy to iterate on."""
from . import config as C

JOBS_FORMAT = (
    "<JOBS>\n"
    '[{"job_id":1,"company":"...","title":"...","location":"...","link":"https://...","why_fit":"one sentence"}, ...]\n'
    "</JOBS>"
)

ANALYSIS_SCHEMA = """{
  "job_id": 1, "company": "...", "title": "...", "link": "https://...",
  "jd_source": "fetched" | "search_snippet",
  "experience_level": "e.g. 5+ years / Senior",
  "jd_summary": "3-4 sentence summary of the role and what the team wants",
  "responsibilities": ["up to 6 short items"],
  "required_skills": ["must-have skills/tools, 6-12 items, exact wording from the JD"],
  "nice_to_have_skills": ["preferred/bonus skills, up to 8"],
  "ats_keywords": ["15-25 exact phrases from the JD: tools, methods, domain terms, soft skills"]
}"""

PROJECTS_SCHEMA = """{
  "job_id": 1,
  "skill_gaps": ["required skills the resume does NOT show"],
  "projects": [
    {
      "name": "short project title",
      "description": "2-3 sentences: what it does and why it matches this JD",
      "skills_demonstrated": ["JD skills this project proves"],
      "gaps_closed": ["skill gaps it closes"],
      "deliverables": ["public GitHub repo with README", "live demo or video", "..."],
      "estimated_effort": "e.g. 1-2 weekends",
      "resume_bullets": ["2-3 bullets: strong verb + tech + outcome with [metric] placeholders"]
    }
  ]
}"""


def main_instructions(n_jobs: int) -> str:
    return f"""You are a job-application strategist: the ORCHESTRATOR of a deep agent.
Goal: for {n_jobs} real job postings produce (a) a job-description analysis with required
skills, (b) up to {C.MAX_PROJECTS} suggested portfolio projects, and (c) a tailored, ATS-optimised resume.

You coordinate specialist sub-agents with the `task` tool. Sub-agents are ISOLATED (they see
only your task description) but share a virtual file system. The candidate's original resume
is already saved at {C.RESUME_PATH}. Tell each sub-agent which files to read and write.

Workflow - follow strictly, in order:
1. PLAN     - call `write_todos` (search, analyse JDs, suggest projects, write resumes, verify, finish).
2. SEARCH   - delegate to `job-search-agent`. It saves {C.JOBS_PATH} and returns a JOBS block.
3. ANALYSE  - delegate to `jd-analyst-agent` for ALL jobs. It writes {C.ANALYSIS_DIR}/job_N.json.
4. PROJECTS - delegate to `project-advisor-agent` for ALL jobs. It writes {C.PROJECTS_DIR}/job_N.json.
5. RESUMES  - delegate to `resume-writer-agent` for ALL jobs. It writes {C.RESUMES_DIR}/job_N.md
              and checks each with the ATS scoring tool.
6. VERIFY   - use `ls` on {C.ANALYSIS_DIR}, {C.PROJECTS_DIR} and {C.RESUMES_DIR}. Each must hold one file per job.
              If any is missing, delegate again for just the missing jobs.
7. FINISH   - final message = ONE short sentence, then the job list copied VERBATIM:
{JOBS_FORMAT}

Hard rules:
- Never invent jobs, links, requirements or candidate experience.
- Do not paste analyses, projects or resumes into your final message; they live in files.
- Keep the job order and job_id numbering (1..N) identical across every file."""


def job_search_prompt(n_jobs: int) -> str:
    return f"""You are a job-search specialist.
Use `internet_search` (several queries: company career pages, Lever, Greenhouse, LinkedIn,
Wellfound...) to find {n_jobs} REAL, CURRENT postings matching the target title, location(s) and
skills you were given. Read {C.RESUME_PATH} first if you need the candidate's skills.

Rules:
- Link must be the actual posting or application page (no search-result or listing pages).
- No duplicates. Prefer postings whose requirements overlap the candidate's skills.
- If fewer than {n_jobs} genuine postings exist, return fewer. Never fabricate.

Steps:
1. Save the list with ONE `write_file` call to {C.JOBS_PATH} (valid JSON array, job_id starting at 1).
2. Reply with ONLY this block (no other text):
{JOBS_FORMAT}"""


def jd_analyst_prompt() -> str:
    return f"""You are a job-description analyst.
Read {C.JOBS_PATH} (the postings) and {C.RESUME_PATH} (candidate resume, for context).
For EACH job:
1. Call `fetch_job_description(link)` to get the JD text. If it returns an ERROR, call
   `internet_search` with company + title + "job description" and use that content instead
   (set "jd_source": "search_snippet"). NEVER invent requirements that are not in the text.
2. Identify the JD: summary, responsibilities, required skills, nice-to-have skills, level,
   and 15-25 ATS keywords. Use the JD's EXACT wording (e.g. "Retrieval-Augmented Generation",
   "CI/CD") - ATS systems match literal phrases.
3. Save ONE `write_file` per job to {C.ANALYSIS_DIR}/job_<job_id>.json with exactly this JSON schema
   (valid JSON only, no comments, no markdown fences):
{ANALYSIS_SCHEMA}

Finish with a one-line confirmation listing the files written."""


def project_advisor_prompt() -> str:
    return f"""You are a technical career coach who designs portfolio projects.
Read {C.RESUME_PATH}, then for EACH job read {C.ANALYSIS_DIR}/job_<N>.json.
1. List "skill_gaps": required skills / keywords the resume does NOT demonstrate.
2. Suggest AT MOST {C.MAX_PROJECTS} projects per job (never more) that:
   - close the biggest gaps AND mirror the JD's responsibilities and domain,
   - are realistic to finish in 1-2 weeks using public data / open-source tools,
   - are different from projects already on the resume,
   - have concrete deliverables (public repo with README, demo, evaluation).
   If there are no gaps, propose projects that show the required skills at the JD's scale.
3. Write 2-3 resume bullets per project: strong action verb + technology + outcome. NEVER invent
   results - use bracketed placeholders like [X%] or [N users] for metrics the candidate must
   fill in after building.
4. Save ONE `write_file` per job to {C.PROJECTS_DIR}/job_<N>.json using exactly this schema
   (valid JSON only, no fences):
{PROJECTS_SCHEMA}

Finish with a one-line confirmation listing the files written."""


def resume_writer_prompt() -> str:
    return f"""You are an expert resume writer specialised in Applicant Tracking Systems (ATS).
For EACH job read {C.RESUME_PATH} (source of truth), {C.ANALYSIS_DIR}/job_<N>.json and
{C.PROJECTS_DIR}/job_<N>.json, then write a resume tailored to that job.

TRUTHFULNESS (non-negotiable):
- Keep every employer, title, date, degree and number from the original resume exactly.
- You may reword, reorder and emphasise real experience, but never invent roles, skills or metrics.
- Skills the candidate lacks must NOT appear in Skills or Experience. They may appear ONLY in the
  Projects section, via the suggested projects (use their resume_bullets, keeping [placeholders]).

ATS FORMAT RULES:
- Plain Markdown, single column. No tables, images, icons, emoji, text boxes.
- Exactly these headings, in this order:  # <Full Name>  (then one contact line with email, phone, location, links),
  ## Professional Summary, ## Skills, ## Work Experience, ## Projects, ## Education.
- Summary (3 lines): the target job title + top 3-4 required skills the candidate truly has + years of experience.
- Skills: grouped lines such as "**Languages:** Python, SQL". Use the JD's exact phrases; write
  acronyms both ways once, e.g. "Retrieval-Augmented Generation (RAG)". Put required skills first.
- Work Experience: reverse chronological; 3-5 bullets per role, each starting with a strong verb;
  reorder/reword to mirror the JD's responsibilities and keywords; keep real metrics.
- Projects: include the suggested projects (maximum {C.MAX_PROJECTS}) with their bullets.
- Length: about one page, 300-750 words. Never pad with invented content.

PROCESS per job:
1. `write_file` to {C.RESUMES_DIR}/job_<N>.md.
2. Call `ats_score_resume(job_id=N)`.
3. If score < {C.ATS_TARGET}: improve the resume (add missing keywords where truthful, fix failed
   checks) by rewriting with `edit_file`, then score again. At most 2 revisions per job.
Finish with one line per job: "job_N: score".""" 
