"""
Tests for file extractor (PDF, DOCX, TXT, MD, CSV, JSON).
"""

import pytest
from tools.file_extractor import extract_text_from_file


def test_extract_txt_and_md():
    content = b"Section 1: Confidentiality Agreement\nAll information shared is private."
    res_txt = extract_text_from_file(content, "contract.txt")
    assert res_txt["file_type"] == "txt"
    assert "Confidentiality Agreement" in res_txt["text"]

    res_md = extract_text_from_file(content, "contract.md")
    assert res_md["file_type"] == "md"
    assert "Confidentiality Agreement" in res_md["text"]


def test_extract_json():
    json_bytes = b'{"matter_id": "M101", "terms": "Non-disclosure required"}'
    res = extract_text_from_file(json_bytes, "data.json")
    assert res["file_type"] == "json"
    assert "M101" in res["text"]


def test_extract_csv():
    csv_bytes = b"header1,header2\nval1,val2"
    res = extract_text_from_file(csv_bytes, "records.csv")
    assert res["file_type"] == "csv"
    assert "header1,header2" in res["text"]
