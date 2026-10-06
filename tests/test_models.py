import json

import pytest

from clara._core import https_origin, is_allowed
from clara.models import Exam, Question, check_password, password_digest


@pytest.fixture
def exam():
    return Exam("Prova", "Escola", "Leia com atenção", "internal", 30, password_digest("responsavel123"), questions=[Question("2 + 2?", ["1", "2", "3", "4"], 3)])


@pytest.mark.parametrize("url", [
    "https://school.edu.evil.test/exam", "https://evil.test/?next=https://school.edu",
    "https://school.edu@evil.test", "https://user@school.edu", "https://school.edu:444/",
    "http://school.edu", "file:///C:/secret", "javascript:alert(1)",
    "data:text/html,hello", "https://sub.school.edu", "https://school.edu\\@evil.test",
    "https://school.edu\n.evil.test", "https://school.edu./",
])
def test_origin_bypasses_rejected(url):
    assert not is_allowed(url, ["https://school.edu"])


def test_origin_normalization():
    assert https_origin("https://SCHOOL.edu:443/exam?q=a") == "https://school.edu"
    assert is_allowed("https://school.edu/next", ["https://school.edu"])
    assert is_allowed("https://school.edu:8443/", ["https://school.edu:8443"])


def test_password():
    digest = password_digest("senha forte")
    assert check_password("senha forte", digest)
    assert not check_password("senha errada", digest)
    assert not check_password("qualquer", "invalid")
    assert password_digest("senha forte") != digest


def test_export_import_and_grade(exam, tmp_path):
    path = tmp_path / "exam.clara.json"
    exam.save(path)
    loaded = Exam.load(path)
    assert loaded == exam
    assert loaded.grade({0: 3})["percent"] == 100
    assert loaded.grade({0: 0})["correct"] == 0
    assert loaded.grade({})["correct"] == 0


def test_invalid_files(tmp_path):
    path = tmp_path / "invalid.json"
    for invalid in ([], None, {"questions": [None]}, {"version": 2}):
        path.write_text(json.dumps(invalid))
        with pytest.raises(ValueError):
            Exam.load(path)


def test_validation(exam):
    exam.minutes = -1
    with pytest.raises(ValueError):
        exam.validate()
    exam.minutes = 30
    exam.questions[0].correct = True
    with pytest.raises(ValueError):
        exam.validate()


def test_external_automatically_includes_start(exam):
    exam.mode = "external"
    exam.start_url = "https://exam.school.edu/start"
    exam.allowed_origins = ["https://login.school.edu/auth"]
    exam.validate()
    assert exam.allowed_origins == ["https://exam.school.edu", "https://login.school.edu"]
