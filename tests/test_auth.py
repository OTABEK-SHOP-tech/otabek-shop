import pytest
from fastapi import HTTPException

from bekstyle.api.auth import verify_telegram_init_data
from bekstyle.config import settings


def test_missing_init_data_rejected(monkeypatch):
    monkeypatch.setattr(settings, "DEV_BROWSER_MODE", False)
    with pytest.raises(HTTPException):
        verify_telegram_init_data("", "42:TEST-TOKEN")


def test_invalid_signature_rejected(monkeypatch):
    monkeypatch.setattr(settings, "DEV_BROWSER_MODE", False)
    raw = "auth_date=9999999999&user=%7B%22id%22%3A123%7D&hash=invalid"
    with pytest.raises(HTTPException):
        verify_telegram_init_data(raw, "42:TEST-TOKEN")


def test_dev_mode_is_disabled_by_default():
    # Production configuration must never silently enable the mock browser user.
    assert type(settings).model_fields["DEV_BROWSER_MODE"].default is False
