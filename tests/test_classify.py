import pytest
from google.genai import errors

from jobs.classify import _is_transient, _tag_with_retry


def _server_error(code: int = 503) -> errors.ServerError:
    return errors.ServerError(code, {"error": {"message": "unavailable"}}, None)


def _client_error(code: int) -> errors.ClientError:
    return errors.ClientError(code, {"error": {"message": "client error"}}, None)


def test_server_error_is_transient():
    assert _is_transient(_server_error(503)) is True


def test_rate_limit_client_error_is_transient():
    assert _is_transient(_client_error(429)) is True


def test_bad_request_client_error_is_not_transient():
    assert _is_transient(_client_error(400)) is False


def test_unrelated_exception_is_not_transient():
    assert _is_transient(ValueError("something else")) is False


async def _flaky_tag_fn(fail_times: int, exc_factory=lambda: _server_error()):
    calls = {"n": 0}

    async def tag_fn(image_bytes, mime_type):
        calls["n"] += 1
        if calls["n"] <= fail_times:
            raise exc_factory()
        return f"success-after-{calls['n']}-calls"

    return tag_fn, calls


@pytest.mark.anyio
async def test_retries_and_succeeds_after_transient_failures():
    tag_fn, calls = await _flaky_tag_fn(fail_times=2)
    result, attempts_used = await _tag_with_retry(b"fake", "image/jpeg", tag_fn=tag_fn)
    assert result == "success-after-3-calls"
    assert attempts_used == 3
    assert calls["n"] == 3


@pytest.mark.anyio
async def test_gives_up_after_max_attempts_of_transient_failures():
    tag_fn, calls = await _flaky_tag_fn(fail_times=99)  # always fails
    with pytest.raises(errors.ServerError):
        await _tag_with_retry(b"fake", "image/jpeg", tag_fn=tag_fn)
    assert calls["n"] == 4  # _MAX_ATTEMPTS in jobs/classify.py


@pytest.mark.anyio
async def test_does_not_retry_non_transient_errors():
    tag_fn, calls = await _flaky_tag_fn(fail_times=99, exc_factory=lambda: _client_error(400))
    with pytest.raises(errors.ClientError):
        await _tag_with_retry(b"fake", "image/jpeg", tag_fn=tag_fn)
    assert calls["n"] == 1


@pytest.fixture
def anyio_backend():
    return "asyncio"
