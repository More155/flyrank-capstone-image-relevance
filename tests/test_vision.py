import json

from schemas import TagStatus, VisionTagOutput
from vision import derive_status, parse_vision_output
from vocab import Subject

CONF_FLOOR = 0.6


def valid_json(**overrides) -> str:
    payload = {
        "subject": "red_fox",
        "category": "mammal",
        "attributes": ["orange fur", "bushy tail"],
        "caption": "A red fox standing in a forest clearing.",
        "confidence": 0.92,
    }
    payload.update(overrides)
    return json.dumps(payload)


def test_valid_output_parses_and_validates():
    parsed, error = parse_vision_output(valid_json())
    assert error is None
    assert isinstance(parsed, VisionTagOutput)
    assert parsed.subject is Subject.RED_FOX


def test_malformed_json_never_raises_and_reports_error():
    parsed, error = parse_vision_output("not valid json at all")
    assert parsed is None
    assert error is not None


def test_confidence_out_of_range_is_rejected():
    parsed, error = parse_vision_output(valid_json(confidence=1.5))
    assert parsed is None
    assert error is not None


def test_unknown_enum_value_is_rejected():
    parsed, error = parse_vision_output(valid_json(subject="dragon"))
    assert parsed is None
    assert error is not None


def test_missing_required_field_is_rejected():
    payload = json.loads(valid_json())
    del payload["caption"]
    parsed, error = parse_vision_output(json.dumps(payload))
    assert parsed is None
    assert error is not None


def test_extra_field_is_rejected():
    parsed, error = parse_vision_output(valid_json(unexpected_field="nope"))
    assert parsed is None
    assert error is not None


def test_derive_status_invalid_output_when_parse_failed():
    assert derive_status(None, CONF_FLOOR) == TagStatus.INVALID_OUTPUT


def test_derive_status_unknown_subject():
    parsed, _ = parse_vision_output(
        valid_json(subject="unknown", confidence=0.4)
    )
    assert derive_status(parsed, CONF_FLOOR) == TagStatus.UNKNOWN_SUBJECT


def test_derive_status_low_confidence():
    parsed, _ = parse_vision_output(valid_json(confidence=0.3))
    assert derive_status(parsed, CONF_FLOOR) == TagStatus.LOW_CONFIDENCE


def test_derive_status_ok():
    parsed, _ = parse_vision_output(valid_json(confidence=0.92))
    assert derive_status(parsed, CONF_FLOOR) == TagStatus.OK
