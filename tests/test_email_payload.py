"""Tests for the shared Resend payload builder.

The send_* functions all post the same shape to Resend; the helper makes
sure `reply_to` is included when configured and omitted otherwise.
That toggle is how we route parent replies to the pilot operator now
and to the daycare director later, without touching code.
"""

from unittest.mock import patch

from backend.services.email import _build_payload


class TestBuildPayload:
    def _settings(self, reply_to: str = "", from_email: str = "Raina <onboarding@raina-pilot.com>"):
        s = type("S", (), {})()
        s.resend_from_email = from_email
        s.resend_reply_to_email = reply_to
        return s

    @patch("backend.services.email.get_settings")
    def test_omits_reply_to_when_unset(self, mock_settings):
        mock_settings.return_value = self._settings(reply_to="")
        payload = _build_payload(
            to_email="parent@example.com",
            subject="hello",
            html_body="<p>hi</p>",
        )
        assert payload["from"] == "Raina <onboarding@raina-pilot.com>"
        assert payload["to"] == ["parent@example.com"]
        assert payload["subject"] == "hello"
        assert payload["html"] == "<p>hi</p>"
        assert "reply_to" not in payload

    @patch("backend.services.email.get_settings")
    def test_includes_reply_to_when_set(self, mock_settings):
        mock_settings.return_value = self._settings(reply_to="hector@example.com")
        payload = _build_payload(
            to_email="parent@example.com",
            subject="welcome",
            html_body="<p>open the portal</p>",
        )
        assert payload["reply_to"] == ["hector@example.com"]

    @patch("backend.services.email.get_settings")
    def test_from_override_wins_over_settings(self, mock_settings):
        mock_settings.return_value = self._settings(reply_to="hector@example.com")
        payload = _build_payload(
            to_email="parent@example.com",
            subject="invoice",
            html_body="<p>bill</p>",
            from_override="Billing <billing@raina-pilot.com>",
        )
        assert payload["from"] == "Billing <billing@raina-pilot.com>"
        # Reply-To still flows through — overriding the from-address doesn't
        # imply you also want to override where replies land.
        assert payload["reply_to"] == ["hector@example.com"]
