"""Characterization tests for the Bookwalker scraping entrypoint scrape_url.

scrape_url builds a requests.Session via get_session_object(url) and calls
``.get`` on it, so we patch ``kce.get_session_object`` (NOT ``kce.requests``) to
inject a fake session — the Session-based path the conftest mock_requests
fixture intentionally does not cover.

Pinned behavior:
  * 200 -> returns a BeautifulSoup over response.content
  * 403 -> raises a PLAIN Exception immediately (tenacity only retries
    requests.exceptions.RequestException, so a 403 hard-block is re-raised at once)
  * a RequestException -> retried stop_after_attempt(3) times, then the
    retry_error_callback returns None (tenacity's wait is neutralized here by
    patching time.sleep so the test is fast).
"""

import pytest

import komga_cover_extractor as kce

pytestmark = pytest.mark.external


class _FakeResp:
    def __init__(self, status_code=200, content=b""):
        self.status_code = status_code
        self.content = content


class _FakeSession:
    """Stand-in for requests.Session: records .get calls, returns/raises queued."""

    def __init__(self, result):
        self._result = result
        self.calls = []

    def get(self, **kwargs):
        self.calls.append(kwargs)
        if isinstance(self._result, Exception):
            raise self._result
        return self._result


def _patch_session(monkeypatch, session):
    monkeypatch.setattr(kce, "get_session_object", lambda url: session)
    return session


class TestScrapeUrl:
    def test_200_returns_soup(self, monkeypatch):
        html = b"<html><body><h1 id='title'>Hello</h1></body></html>"
        session = _patch_session(monkeypatch, _FakeSession(_FakeResp(200, html)))
        soup = kce.scrape_url("https://bookwalker.jp/series/123")
        # BeautifulSoup object: can query the parsed DOM
        assert soup is not None
        assert soup.find(id="title").get_text() == "Hello"
        assert len(session.calls) == 1

    def test_403_raises_immediately_no_retry(self, monkeypatch):
        session = _patch_session(monkeypatch, _FakeSession(_FakeResp(403, b"")))
        with pytest.raises(Exception, match="rate-limited"):
            kce.scrape_url("https://bookwalker.jp/series/123")
        # 403 is re-raised on the FIRST attempt (no retry loop)
        assert len(session.calls) == 1

    def test_request_exception_retries_then_returns_none(self, monkeypatch):
        # Neutralize tenacity's fixed 2s wait so the 3 attempts run instantly.
        monkeypatch.setattr("time.sleep", lambda *_a, **_k: None)
        err = kce.requests.exceptions.ConnectionError("connection reset")
        session = _patch_session(monkeypatch, _FakeSession(err))
        result = kce.scrape_url("https://bookwalker.jp/series/123")
        # After 3 failed attempts the retry_error_callback returns None.
        assert result is None
        assert len(session.calls) == 3

    def test_passes_headers_when_provided(self, monkeypatch):
        session = _patch_session(monkeypatch, _FakeSession(_FakeResp(200, b"<html></html>")))
        kce.scrape_url("https://bookwalker.jp/x", headers={"X-Test": "1"})
        # None-valued params are filtered out; provided headers are forwarded.
        assert session.calls[0].get("headers") == {"X-Test": "1"}
        assert "cookies" not in session.calls[0]
