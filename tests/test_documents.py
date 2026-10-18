import io

import docx
import pytest

from jobagent.documents import extract_text, md_to_docx


def test_txt_extract():
    assert extract_text("cv.txt", b"hello") == "hello"


def test_unsupported_format():
    with pytest.raises(ValueError):
        extract_text("cv.exe", b"x")


def test_md_to_docx_roundtrip():
    data = md_to_docx("# Cover Letters\n\n## 1. Acme\n**Subject:** Hi\n\n- point\nBody text")
    assert data[:2] == b"PK"  # valid zip/docx
    text = extract_text("out.docx", data)
    assert "Cover Letters" in text and "Subject:" in text and "Body text" in text
