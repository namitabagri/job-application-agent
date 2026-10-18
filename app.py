"""Streamlit UI for the Job Application Agent.   Run:  streamlit run app.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

import streamlit as st

from jobagent import config
from jobagent.documents import extract_text, md_to_docx
from jobagent.exports import build_zip, jobs_dataframe, report_markdown
from jobagent.runner import run_job_agent

st.set_page_config(page_title="Job Application Assistant", page_icon="🎯", layout="wide")
st.session_state.setdefault("result", None)

st.title("🎯 Job Application Assistant")
st.caption("Deep Agents: find jobs → analyse JDs → suggest projects → ATS-optimised resume per job")

# ---- sidebar ---------------------------------------------------------------------
with st.sidebar:
    st.header("Setup")
    missing = config.missing_keys()
    if missing:
        st.error("Missing: " + ", ".join(missing) + "\n\nAdd them to your `.env` file.")
    else:
        st.success(f"API keys found. Model: `{config.model_name()}`")
    n_jobs = st.slider("Jobs to process", 1, config.MAX_JOBS_LIMIT, config.DEFAULT_JOBS,
                       help="Each job = JD analysis + projects + tailored resume. More jobs = slower run.")
    st.caption("ATS score is a transparent proxy (keyword coverage + format checks), not a real ATS.")

# ---- inputs ----------------------------------------------------------------------
c0, c1, c2 = st.columns([2, 1, 1])
with c0:
    uploaded = st.file_uploader("Upload your resume (PDF/DOCX/TXT)", type=["pdf", "docx", "txt"])
with c1:
    title = st.text_input("Target title", "Senior Machine Learning Engineer")
with c2:
    location = st.text_input("Target location(s)", "Bangalore OR Remote")
skills = st.text_area("Add/override skills (optional)", "", placeholder="Python, PyTorch, LLMs, RAG, FastAPI")

if st.button("Run", type="primary", disabled=not uploaded or bool(missing)):
    st.session_state.result = None
    try:
        resume_text = extract_text(uploaded.name, uploaded.getvalue())
        with st.spinner("Searching jobs, analysing JDs, designing projects, tailoring resumes (3-8 min)..."):
            st.session_state.result = run_job_agent(resume_text, title, location, skills, n_jobs=n_jobs)
        st.success("Done!")
    except Exception as e:
        st.error(f"Error: {e}")


def badges(items, color):
    return " ".join(f":{color}-badge[{str(i).replace(']', ')')}]" for i in items) or "—"


# ---- results ---------------------------------------------------------------------
result = st.session_state.result
if result:
    st.header("Results")
    if result.reports:
        st.dataframe(
            jobs_dataframe(result), hide_index=True, use_container_width=True,
            column_config={
                "Apply": st.column_config.LinkColumn("Apply", display_text="Apply ↗"),
                "ATS before": st.column_config.ProgressColumn("ATS before", min_value=0, max_value=100, format="%d"),
                "ATS after": st.column_config.ProgressColumn("ATS after", min_value=0, max_value=100, format="%d"),
            },
        )
        st.download_button("⬇️ Download everything (ZIP: resumes .docx/.md + analysis + CSV)",
                           data=build_zip(result), file_name="job_application_pack.zip", mime="application/zip")
        st.info("**Before you apply:** suggested projects are *plans*. Build them first, replace any "
                "`[placeholders]` with your real results, and never list skills you can't speak to in an interview.")

        tabs = st.tabs([f"{r.job_id}. {r.job['company']}" for r in result.reports])
        for tab, r in zip(tabs, result.reports):
            with tab:
                st.subheader(f"{r.job['title']} — {r.job['company']}")
                st.markdown(f"📍 {r.job['location']} · [Open posting]({r.job['link']}) · _{r.job['why_fit']}_")
                if r.ats_before and r.ats_after:
                    m1, m2, m3 = st.columns(3)
                    m1.metric("ATS score (original resume)", r.ats_before["score"])
                    m2.metric("ATS score (tailored resume)", r.ats_after["score"],
                              delta=r.ats_after["score"] - r.ats_before["score"])
                    m3.metric("Required skills covered", f"{len(r.ats_after['matched_required'])}/"
                              f"{len(r.ats_after['matched_required']) + len(r.ats_after['missing_required'])}")

                t1, t2, t3 = st.tabs(["📋 JD & skills", "🛠️ Suggested projects", "📄 Tailored resume"])
                with t1:
                    a = r.analysis
                    if a:
                        st.markdown(f"**Level:** {a.get('experience_level', '—')} · "
                                    f"**JD source:** {a.get('jd_source', '—')}")
                        st.write(a.get("jd_summary", ""))
                        if a.get("responsibilities"):
                            st.markdown("**Responsibilities**\n" + "\n".join(f"- {x}" for x in a["responsibilities"]))
                        have = [s for s in a.get("required_skills", []) if s not in r.gaps]
                        st.markdown("**Required skills** — :green[you have] / :red[gaps]")
                        st.markdown(badges(have, "green") + " " + badges(r.gaps, "red"))
                        st.markdown("**Nice to have**")
                        st.markdown(badges(a.get("nice_to_have_skills", []), "gray"))
                        with st.expander("ATS keywords"):
                            st.write(", ".join(a.get("ats_keywords", [])))
                    else:
                        st.warning("No JD analysis produced for this job.")
                with t2:
                    if r.projects:
                        for i, p in enumerate(r.projects, 1):
                            with st.expander(f"Project {i}: {p.get('name', '')}  ·  {p.get('estimated_effort', '')}", expanded=True):
                                st.write(p.get("description", ""))
                                st.markdown("**Skills demonstrated:** " + badges(p.get("skills_demonstrated", []), "blue"))
                                st.markdown("**Deliverables**\n" + "\n".join(f"- {d}" for d in p.get("deliverables", [])))
                                st.markdown("**Resume bullets**\n" + "\n".join(f"- {b}" for b in p.get("resume_bullets", [])))
                    else:
                        st.info("No project suggestions produced.")
                with t3:
                    if r.resume_md:
                        st.markdown(r.resume_md)
                        if r.ats_after.get("missing_required") or r.ats_after.get("missing_other"):
                            st.caption("Still missing (kept out because they are not truthful for you or not covered by a project): "
                                       + ", ".join(r.ats_after["missing_required"] + r.ats_after["missing_other"][:10]))
                        d1, d2, d3 = st.columns(3)
                        d1.download_button("Resume .docx", md_to_docx(r.resume_md), f"resume_job_{r.job_id}.docx",
                                           "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                           key=f"docx{r.job_id}")
                        d2.download_button("Resume .md", r.resume_md, f"resume_job_{r.job_id}.md", "text/markdown",
                                           key=f"md{r.job_id}")
                        d3.download_button("Analysis .md", report_markdown(r), f"analysis_job_{r.job_id}.md",
                                           "text/markdown", key=f"an{r.job_id}")
                    else:
                        st.warning("No tailored resume produced for this job.")
    for w in result.warnings:
        st.warning(w)
    with st.expander("Debug: raw agent output"):
        st.code(result.final_text or "(empty)")
