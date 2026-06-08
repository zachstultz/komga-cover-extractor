"""Characterization tests for the Komga HTTP integration.

Pins get_komga_libraries / scan_komga_library against mocked requests. These use
``requests.get`` / ``requests.post`` directly (with HTTPBasicAuth + a tenacity
retry that only fires on a "104" connection-reset), so the conftest
``mock_requests`` fixture (which patches ``kce.requests.get/post``) covers them.

All tests are marked ``external``: run with ``-m external`` (or together with the
default suite). Credentials are set on the kce namespace per the project's
``from settings import *`` convention; the autouse isolated_globals fixture
restores them.
"""

import pytest

import komga_cover_extractor as kce

pytestmark = pytest.mark.external


def _set_creds(monkeypatch):
    monkeypatch.setattr(kce, "komga_ip", "http://localhost")
    monkeypatch.setattr(kce, "komga_port", "25600")
    monkeypatch.setattr(kce, "komga_login_email", "user@example.com")
    monkeypatch.setattr(kce, "komga_login_password", "secret")


# --------------------------------------------------------------------------- #
# get_komga_libraries
# --------------------------------------------------------------------------- #

class TestGetKomgaLibraries:
    def test_missing_ip_returns_none_no_request(self, monkeypatch, mock_requests):
        # FLAG: a guard-failure (missing ip/email/password) returns None — NOT the
        # empty list `results`. Callers must handle the None vs [] distinction.
        monkeypatch.setattr(kce, "komga_ip", "")
        assert kce.get_komga_libraries() is None
        assert mock_requests.get_calls == []

    def test_missing_email_returns_none(self, monkeypatch, mock_requests):
        monkeypatch.setattr(kce, "komga_ip", "http://localhost")
        monkeypatch.setattr(kce, "komga_login_email", "")
        assert kce.get_komga_libraries() is None

    def test_missing_password_returns_none(self, monkeypatch, mock_requests):
        monkeypatch.setattr(kce, "komga_ip", "http://localhost")
        monkeypatch.setattr(kce, "komga_login_email", "user@example.com")
        monkeypatch.setattr(kce, "komga_login_password", "")
        assert kce.get_komga_libraries() is None

    def test_200_returns_json_payload(self, monkeypatch, mock_requests, fake_response):
        _set_creds(monkeypatch)
        payload = [{"id": "lib1", "name": "Manga"}, {"id": "lib2", "name": "Novels"}]
        mock_requests.get_returns(fake_response(status_code=200, json_data=payload))
        assert kce.get_komga_libraries() == payload

    def test_200_uses_port_in_url(self, monkeypatch, mock_requests, fake_response):
        _set_creds(monkeypatch)
        mock_requests.get_returns(fake_response(status_code=200, json_data=[]))
        kce.get_komga_libraries()
        # url is the first positional arg to requests.get
        (args, kwargs) = mock_requests.get_calls[0]
        url = args[0] if args else kwargs.get("url")
        assert url == "http://localhost:25600/api/v1/libraries"

    def test_non_200_returns_empty_list(self, monkeypatch, mock_requests, fake_response):
        # FLAG: a non-200 response leaves `results` as the initial [] and returns it,
        # so a server error is indistinguishable from "no libraries" at the call site.
        _set_creds(monkeypatch)
        mock_requests.get_returns(fake_response(status_code=500, text="boom"))
        assert kce.get_komga_libraries() == []

    def test_no_port_uses_bare_ip(self, monkeypatch, mock_requests, fake_response):
        monkeypatch.setattr(kce, "komga_ip", "http://localhost")
        monkeypatch.setattr(kce, "komga_port", "")
        monkeypatch.setattr(kce, "komga_login_email", "user@example.com")
        monkeypatch.setattr(kce, "komga_login_password", "secret")
        mock_requests.get_returns(fake_response(status_code=200, json_data=[]))
        kce.get_komga_libraries()
        (args, kwargs) = mock_requests.get_calls[0]
        url = args[0] if args else kwargs.get("url")
        assert url == "http://localhost/api/v1/libraries"


# --------------------------------------------------------------------------- #
# scan_komga_library
# --------------------------------------------------------------------------- #

class TestScanKomgaLibrary:
    def test_missing_ip_returns_none_no_request(self, monkeypatch, mock_requests):
        monkeypatch.setattr(kce, "komga_ip", "")
        assert kce.scan_komga_library("lib1", "Manga") is None
        assert mock_requests.post_calls == []

    def test_202_posts_scan_url(self, monkeypatch, mock_requests, fake_response):
        _set_creds(monkeypatch)
        mock_requests.post_returns(fake_response(status_code=202))
        # returns None regardless; the observable is the POST to the scan endpoint
        assert kce.scan_komga_library("lib1", "Manga") is None
        (args, kwargs) = mock_requests.post_calls[0]
        url = args[0] if args else kwargs.get("url")
        assert url == "http://localhost:25600/api/v1/libraries/lib1/scan"

    def test_non_202_does_not_raise(self, monkeypatch, mock_requests, fake_response):
        _set_creds(monkeypatch)
        mock_requests.post_returns(fake_response(status_code=500, text="nope"))
        # error path logs via send_message but does not raise
        assert kce.scan_komga_library("lib1", "Manga") is None
        assert len(mock_requests.post_calls) == 1
