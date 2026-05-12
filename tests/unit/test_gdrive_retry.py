"""Unit tests for syft_client.sync.connections.drive.gdrive_retry.

Focus: the retry helpers must recover from socket-level transients
(ConnectionResetError, BrokenPipeError, etc.) that surface when httplib2's
cached keepalive connection is closed server-side. Pre-fix these escaped the
retry loop entirely; this test pins the behavior so it doesn't regress.
"""

import http.client
import socket
import ssl
from unittest.mock import Mock, patch

import pytest
from googleapiclient.errors import HttpError

from syft_client.sync.connections.drive.gdrive_retry import (
    RETRYABLE_TRANSPORT_ERRORS,
    batch_execute_with_retries,
    execute_with_retries,
    is_retryable_error,
    next_chunk_with_retries,
)


def _http_error(status: int) -> HttpError:
    resp = Mock()
    resp.status = status
    resp.reason = "test"
    return HttpError(resp, b"{}")


TRANSPORT_INSTANCES = [
    ConnectionResetError("peer reset"),
    ConnectionAbortedError("aborted"),
    BrokenPipeError("epipe"),
    TimeoutError("timed out"),
    socket.timeout("sock timeout"),
    ssl.SSLError("ssl"),
    http.client.RemoteDisconnected("remote disconnected"),
    http.client.BadStatusLine("bad status"),
]


@pytest.fixture(autouse=True)
def _no_sleep():
    """Patch time.sleep so tests run instantly."""
    with patch("syft_client.sync.connections.drive.gdrive_retry.time.sleep"):
        yield


# ---------- is_retryable_error ----------------------------------------------


@pytest.mark.parametrize("err", TRANSPORT_INSTANCES)
def test_is_retryable_error_transport(err):
    assert is_retryable_error(err) is True


@pytest.mark.parametrize("status", [500, 502, 503, 429])
def test_is_retryable_error_retryable_http(status):
    assert is_retryable_error(_http_error(status)) is True


@pytest.mark.parametrize("status", [400, 401, 403, 404, 409])
def test_is_retryable_error_non_retryable_http(status):
    assert is_retryable_error(_http_error(status)) is False


def test_is_retryable_error_unrelated_exception():
    assert is_retryable_error(ValueError("nope")) is False


# ---------- execute_with_retries --------------------------------------------


@pytest.mark.parametrize("err", TRANSPORT_INSTANCES)
def test_execute_with_retries_recovers_from_transport_error(err):
    """After Fix A, transport errors are caught and retried."""
    request = Mock()
    request.execute.side_effect = [err, {"ok": True}]

    result = execute_with_retries(request, initial_delay=0, max_delay=0)

    assert result == {"ok": True}
    assert request.execute.call_count == 2


def test_execute_with_retries_exhausts_then_raises():
    request = Mock()
    request.execute.side_effect = ConnectionResetError("peer reset")

    with pytest.raises(ConnectionResetError):
        execute_with_retries(request, max_retries=2, initial_delay=0, max_delay=0)

    # max_retries=2 means 1 initial attempt + 2 retries = 3 total.
    assert request.execute.call_count == 3


def test_execute_with_retries_non_retryable_http_raises_immediately():
    request = Mock()
    request.execute.side_effect = _http_error(404)

    with pytest.raises(HttpError):
        execute_with_retries(request, initial_delay=0, max_delay=0)

    assert request.execute.call_count == 1


def test_execute_with_retries_retries_retryable_http():
    request = Mock()
    request.execute.side_effect = [_http_error(503), _http_error(500), {"ok": True}]

    result = execute_with_retries(request, initial_delay=0, max_delay=0)

    assert result == {"ok": True}
    assert request.execute.call_count == 3


def test_execute_with_retries_mixed_error_types():
    """Sequence mixing transport and HTTP transients both retry."""
    request = Mock()
    request.execute.side_effect = [
        ConnectionResetError("reset"),
        _http_error(503),
        BrokenPipeError("epipe"),
        {"ok": True},
    ]

    result = execute_with_retries(request, max_retries=5, initial_delay=0, max_delay=0)

    assert result == {"ok": True}
    assert request.execute.call_count == 4


def test_execute_with_retries_passes_through_unrelated_exception():
    """Non-transport, non-HttpError exceptions are not caught by the retry."""
    request = Mock()
    request.execute.side_effect = ValueError("nope")

    with pytest.raises(ValueError):
        execute_with_retries(request, initial_delay=0, max_delay=0)

    assert request.execute.call_count == 1


# ---------- next_chunk_with_retries -----------------------------------------


@pytest.mark.parametrize("err", TRANSPORT_INSTANCES)
def test_next_chunk_with_retries_recovers_from_transport_error(err):
    downloader = Mock()
    downloader.next_chunk.side_effect = [err, (Mock(), True)]

    status, done = next_chunk_with_retries(downloader, initial_delay=0, max_delay=0)

    assert done is True
    assert downloader.next_chunk.call_count == 2


def test_next_chunk_with_retries_exhausts_then_raises():
    downloader = Mock()
    downloader.next_chunk.side_effect = BrokenPipeError("epipe")

    with pytest.raises(BrokenPipeError):
        next_chunk_with_retries(downloader, max_retries=1, initial_delay=0, max_delay=0)

    assert downloader.next_chunk.call_count == 2


# ---------- batch_execute_with_retries --------------------------------------


@pytest.mark.parametrize("err", TRANSPORT_INSTANCES)
def test_batch_execute_with_retries_recovers_from_transport_error(err):
    batch = Mock()
    batch.execute.side_effect = [err, None]

    batch_execute_with_retries(batch, initial_delay=0, max_delay=0)

    assert batch.execute.call_count == 2


def test_batch_execute_with_retries_exhausts_then_raises():
    batch = Mock()
    batch.execute.side_effect = ConnectionResetError("reset")

    with pytest.raises(ConnectionResetError):
        batch_execute_with_retries(batch, max_retries=0, initial_delay=0, max_delay=0)

    assert batch.execute.call_count == 1


# ---------- module-level invariants -----------------------------------------


def test_all_listed_transport_errors_are_recognized_as_retryable():
    """RETRYABLE_TRANSPORT_ERRORS and is_retryable_error must agree."""
    for cls in RETRYABLE_TRANSPORT_ERRORS:
        # ssl.SSLError requires an arg; others accept a string. Both work.
        instance = cls("x") if cls is not http.client.BadStatusLine else cls("x")
        assert is_retryable_error(instance) is True, cls
