from unittest.mock import AsyncMock

from donats import da_auth, settings
from donats.da_auth import get_access_token


async def test_get_access_token_returns_env_token_when_not_expired(monkeypatch) -> None:
    monkeypatch.setattr(settings, 'DA_ACCESS_TOKEN', 'env-token')
    monkeypatch.setattr(settings, 'DA_TOKEN_EXPIRES_AT', '')

    token = await get_access_token(AsyncMock())

    assert token == 'env-token'


async def test_get_access_token_refreshes_when_expired(monkeypatch) -> None:
    monkeypatch.setattr(settings, 'DA_ACCESS_TOKEN', 'stale-token')
    monkeypatch.setattr(settings, 'DA_TOKEN_EXPIRES_AT', '1')
    monkeypatch.setattr(settings, 'DA_REFRESH_TOKEN', 'refresh-token')

    async def fake_refresh(_session):
        return 'fresh-token'

    monkeypatch.setattr(da_auth, 'refresh_access_token', fake_refresh)

    token = await get_access_token(AsyncMock())

    assert token == 'fresh-token'


async def test_get_access_token_returns_stale_token_without_refresh(monkeypatch) -> None:
    monkeypatch.setattr(settings, 'DA_ACCESS_TOKEN', 'stale-token')
    monkeypatch.setattr(settings, 'DA_TOKEN_EXPIRES_AT', '1')
    monkeypatch.setattr(settings, 'DA_REFRESH_TOKEN', '')

    token = await get_access_token(AsyncMock())

    assert token == 'stale-token'
