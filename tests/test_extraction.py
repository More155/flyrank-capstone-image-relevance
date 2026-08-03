import json

from extraction import parse_extraction_output
from schemas import SubjectExtraction
from vocab import Subject


def valid_json(**overrides) -> str:
    payload = {"subject": "red_fox", "confidence": 0.95}
    payload.update(overrides)
    return json.dumps(payload)


def test_valid_output_parses_and_validates():
    parsed, error = parse_extraction_output(valid_json())
    assert error is None
    assert isinstance(parsed, SubjectExtraction)
    assert parsed.subject is Subject.RED_FOX


def test_malformed_json_never_raises_and_reports_error():
    parsed, error = parse_extraction_output("not json")
    assert parsed is None
    assert error is not None


def test_unknown_enum_value_is_rejected():
    parsed, error = parse_extraction_output(valid_json(subject="dragon"))
    assert parsed is None
    assert error is not None


def test_confidence_out_of_range_is_rejected():
    parsed, error = parse_extraction_output(valid_json(confidence=1.2))
    assert parsed is None
    assert error is not None


def test_extra_field_is_rejected():
    parsed, error = parse_extraction_output(valid_json(unexpected="nope"))
    assert parsed is None
    assert error is not None


def test_unknown_subject_is_a_valid_result():
    parsed, error = parse_extraction_output(valid_json(subject="unknown", confidence=0.9))
    assert error is None
    assert parsed.subject is Subject.UNKNOWN
