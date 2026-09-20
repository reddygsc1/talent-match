import pytest
from src.parsers import extract_resume


def test_txt_resume():
    assert extract_resume("resume.txt", b"Built production APIs") == "Built production APIs"


def test_empty_resume_rejected():
    with pytest.raises(ValueError, match="No text"):
        extract_resume("resume.txt", b"  ")


def test_unsupported_file_rejected():
    with pytest.raises(ValueError, match="Supported"):
        extract_resume("resume.rtf", b"hello")
