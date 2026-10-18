"""Headless runner.  Example:
    python cli.py --resume sample_data/sample_resume.txt \
        --title "Senior Machine Learning Engineer" --location "Bangalore OR Remote" --jobs 3
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from jobagent import config
from jobagent.documents import extract_text, md_to_docx
from jobagent.exports import _slug, jobs_dataframe, report_all_markdown
from jobagent.runner import run_job_agent


def main() -> int:
    p = argparse.ArgumentParser(description="Job Application Agent (CLI)")
    p.add_argument("--resume", required=True, help="Path to resume (.pdf/.docx/.txt)")
    p.add_argument("--title", default="Senior Machine Learning Engineer")
    p.add_argument("--location", default="Bangalore OR Remote")
    p.add_argument("--skills", default="")
    p.add_argument("--jobs", type=int, default=config.DEFAULT_JOBS)
    p.add_argument("--out", default="outputs", help="Output directory")
    args = p.parse_args()

    missing = config.missing_keys()
    if missing:
        print("Missing environment variables:", ", ".join(missing), "(set them in .env)")
        return 1

    path = Path(args.resume)
    resume_text = extract_text(path.name, path.read_bytes())

    print("Running agent (this can take several minutes)...")
    result = run_job_agent(resume_text, args.title, args.location, args.skills, n_jobs=args.jobs)

    out = Path(args.out)
    (out / "resumes").mkdir(parents=True, exist_ok=True)
    df = jobs_dataframe(result)
    df.to_csv(out / "jobs.csv", index=False)
    (out / "job_application_pack.md").write_text(report_all_markdown(result), encoding="utf-8")
    for r in result.reports:
        if r.resume_md:
            base = out / "resumes" / f"{r.job_id}_{_slug(r.job['company'])}"
            base.with_suffix(".md").write_text(r.resume_md, encoding="utf-8")
            base.with_suffix(".docx").write_bytes(md_to_docx(r.resume_md))
    print(df.drop(columns=["Apply"]).to_string(index=False) if not df.empty else "No jobs found.")
    for w in result.warnings:
        print("WARNING:", w)
    print(f"\nSaved results to ./{out}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
