from jobagent.parsing import (
    extract_jobs_from_text, get_file_content, normalize_jobs, parse_json_text,
)

GOOD = '''Here you go.
<JOBS>
```json
[{"company":"Acme","title":"ML Eng","location":"Remote","link":"https://acme.com/j/1","why_fit":"Uses PyTorch"},
 {"Company":"Beta","Title":"AI Eng","Location":"Bangalore","Link":"https://beta.io/j/2","Good Match":"RAG experience"},]
```
</JOBS>'''


def test_extract_handles_fences_and_trailing_comma():
    assert len(extract_jobs_from_text(GOOD)) == 2


def test_extract_returns_empty_when_missing():
    assert extract_jobs_from_text("no jobs here") == []
    assert extract_jobs_from_text("") == []


def test_normalize_numbers_dedupes_validates_and_keeps_reason():
    items = [
        {"company": "A", "title": "T", "link": "https://x.com/1", "why_fit": "good"},
        {"company": "A", "title": "T", "link": "https://x.com/1"},   # duplicate
        {"company": "B", "title": "T", "link": "not-a-url"},          # invalid
        "garbage",
        {"company": "C", "link": "https://x.com/3"},
    ]
    out = normalize_jobs(items)
    assert [j["job_id"] for j in out] == [1, 2]
    assert out[0]["why_fit"] == "good"


def test_normalize_caps_at_limit():
    assert len(normalize_jobs([{"link": f"https://x.com/{i}"} for i in range(10)], limit=3)) == 3


def test_parse_json_text_variants():
    assert parse_json_text('```json\n{"a": 1,}\n```') == {"a": 1}
    assert parse_json_text("not json") is None


def test_get_file_content_shapes():
    assert get_file_content({"/f.md": {"content": "hi"}}, "/f.md") == "hi"
    assert get_file_content({"f.md": {"content": ["a", "b"]}}, "/f.md") == "a\nb"
    assert get_file_content({}, "/f.md") == ""
