"""Characterization tests for the Discord notification layer.

Pins send_discord_message (webhook execution + reset behavior) and
group_notification (the batching buffer used throughout the pipeline). The
discord-webhook library is never actually hit: we patch
``DiscordWebhook.execute`` at the class level (send_discord_message resets the
global ``webhook_obj`` to a fresh instance after every call, so an instance-level
patch would be lost — the class-level patch survives).
"""

import pytest

import komga_cover_extractor as kce

pytestmark = pytest.mark.external


def _make_embed(title="t", desc="d"):
    return kce.Embed(kce.DiscordEmbed(title=title, description=desc), None)


class TestSendDiscordMessage:
    def test_no_webhook_configured_returns_false(self, monkeypatch):
        # No url, no passed_webhook, empty discord_webhook_url -> pick_webhook
        # yields None, the body is skipped, sent_status stays False.
        monkeypatch.setattr(kce, "discord_webhook_url", [])
        calls = []
        monkeypatch.setattr(kce.DiscordWebhook, "execute",
                            lambda self, *a, **k: calls.append(self))
        assert kce.send_discord_message("hello") is False
        assert calls == []

    def test_passed_webhook_executes_and_returns_true(self, monkeypatch):
        executed = []
        monkeypatch.setattr(
            kce.DiscordWebhook, "execute",
            lambda self, *a, **k: executed.append(getattr(self, "content", None)),
        )
        result = kce.send_discord_message("hi there", passed_webhook="http://example/wh")
        assert result is True
        assert executed == ["hi there"]

    def test_webhook_obj_reset_after_send(self, monkeypatch):
        monkeypatch.setattr(kce.DiscordWebhook, "execute", lambda self, *a, **k: None)
        kce.send_discord_message("hi", passed_webhook="http://example/wh")
        # After every call the global webhook_obj is reset to a fresh url=None object.
        assert kce.webhook_obj.url is None

    def test_execute_exception_returns_false_and_resets(self, monkeypatch):
        def _boom(self, *a, **k):
            raise RuntimeError("network down")

        monkeypatch.setattr(kce.DiscordWebhook, "execute", _boom)
        # The exception is swallowed; sent_status False is returned, obj reset.
        assert kce.send_discord_message("hi", passed_webhook="http://example/wh") is False
        assert kce.webhook_obj.url is None


class TestGroupNotification:
    def test_appends_embed_to_buffer(self, monkeypatch):
        monkeypatch.setattr(kce, "discord_embed_limit", 10)
        embed = _make_embed()
        out = kce.group_notification([], embed)
        assert out == [embed]
        assert len(out) == 1

    def test_does_not_duplicate_same_embed(self, monkeypatch):
        monkeypatch.setattr(kce, "discord_embed_limit", 10)
        embed = _make_embed()
        notifications = kce.group_notification([], embed)
        # FLAG: dedup is identity-based (`embed not in notifications`); re-passing
        # the SAME object does not append it again.
        notifications = kce.group_notification(notifications, embed)
        assert notifications == [embed]

    def test_flushes_when_at_limit(self, monkeypatch):
        # When the buffer is already at the embed limit, group_notification flushes
        # it via send_discord_message before appending the new embed.
        monkeypatch.setattr(kce, "discord_embed_limit", 1)
        monkeypatch.setattr(kce, "discord_webhook_url", ["http://example/wh"])
        sent = []
        monkeypatch.setattr(kce, "send_discord_message",
                            lambda *a, **k: (sent.append(a) or True))
        first = _make_embed("first")
        buffer = [first]  # len 1 >= limit 1 -> triggers flush
        second = _make_embed("second")
        out = kce.group_notification(buffer, second)
        assert sent, "expected a flush via send_discord_message"
        # the old buffer was flushed (emptied) and only the new embed remains
        assert out == [second]
