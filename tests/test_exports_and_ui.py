import io
import zipfile
from pathlib import Path

from deepagents.backends.utils import create_file_data
from streamlit.testing.v1 import AppTest

import test_agent_wiring as t
from jobagent.exports import build_zip, jobs_dataframe, report_all_markdown
from jobagent.runner import build_reports

ROOT = Path(__file__).resolve().parents[1]


def make_result():
    files = {"/resume.txt": create_file_data(t.RESUME)}
    for n in (1, 2):
        files[f"/analysis/job_{n}.json"] = create_file_data(t.analysis(n))
        files[f"/projects/job_{n}.json"] = create_file_data(t.projects(n))
        files[f"/resumes/job_{n}.md"] = create_file_data(t.TAILORED)
    return build_reports(t.JOBS, files, t.RESUME)


def test_reports_and_exports():
    result = make_result()
    assert result.warnings == []
    df = jobs_dataframe(result)
    assert list(df["Company"]) == ["Acme AI", "Beta Labs"]
    assert (df["ATS after"] > df["ATS before"]).all()
    md = report_all_markdown(result)
    assert "Suggested projects" in md and "Kubernetes" in md

    z = zipfile.ZipFile(io.BytesIO(build_zip(result)))
    names = z.namelist()
    assert "job_application_pack.md" in names and "jobs.csv" in names
    assert any(n.startswith("resumes/1_acme-ai") and n.endswith(".docx") for n in names)


def test_missing_files_produce_warnings():
    result = build_reports(t.JOBS, {}, t.RESUME)
    assert len(result.warnings) == 6  # 3 per job: analysis, projects, resume


def test_streamlit_app_renders_results():
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30)
    at.session_state["result"] = make_result()
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert any("Results" in h.value for h in at.header)
    assert len(at.tabs) >= 2 + 6          # 2 job tabs + 3 inner tabs per job
