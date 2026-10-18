from jobagent.ats import contains_keyword, score_resume

ANALYSIS = {
    "required_skills": ["Python", "PyTorch", "Retrieval-Augmented Generation", "Kubernetes"],
    "nice_to_have_skills": ["vLLM"],
    "ats_keywords": ["CI/CD", "C++", "LLM"],
}
GOOD = """# Jane Doe
jane@example.com
## Professional Summary
ML engineer.
## Skills
Python, PyTorch, Retrieval Augmented Generation (RAG), Kubernetes, vLLM, CI/CD, LLMs
## Work Experience
- Built things.
## Education
B.Tech
"""


def test_keyword_matching_rules():
    assert contains_keyword("I use Python daily", "python")
    assert contains_keyword("fine-tuned LLMs", "LLM")                  # plural
    assert contains_keyword("retrieval augmented generation", "Retrieval-Augmented Generation")
    assert contains_keyword("wrote C++ code", "C++")
    assert not contains_keyword("JavaScript only", "Java")             # no partial words
    assert not contains_keyword("", "Python")


def test_score_rewards_keywords_and_reports_missing():
    low = score_resume("# Bob\nbob@x.com\n## Skills\nExcel", ANALYSIS)
    high = score_resume(GOOD, ANALYSIS)
    assert high["score"] > low["score"]
    assert "Kubernetes" in low["missing_required"]
    assert high["missing_required"] == []
    assert high["checks"]["has_email"] and high["checks"]["no_tables"]


def test_structure_flags_tables():
    r = score_resume("| a | b |\n| c | d |", ANALYSIS)
    assert r["checks"]["no_tables"] is False
