import logging
import time

import aiohttp

from donats import settings

logger = logging.getLogger(__name__)

TOKEN_URL = 'https://www.donationalerts.com/oauth/token'  # noqa: S105 - URL, not a secret


async def refresh_access_token(session: aiohttp.ClientSession) -> str:
    """Refresh the OAuth access token from env; .env must be updated with new values."""
    async with session.post(
        TOKEN_URL,
        data={
            'grant_type': 'refresh_token',
            'client_id': settings.DA_CLIENT_ID,
            'client_secret': settings.DA_CLIENT_SECRET,
            'refresh_token': settings.DA_REFRESH_TOKEN,
        },
    ) as resp:
        resp.raise_for_status()
        data = await resp.json()
    logger.warning(
        'Access token refreshed in memory. Update DA_ACCESS_TOKEN, '
        'DA_REFRESH_TOKEN and DA_TOKEN_EXPIRES_AT in .env with the new values.'
    )
    return data['access_token']


def _expired() -> bool:
    raw = settings.DA_TOKEN_EXPIRES_AT
    if not raw:
        return False
    try:
        return float(raw) < time.time()
    except ValueError:
        return False


async def get_access_token(session: aiohttp.ClientSession) -> str:
    """OAuth access token from env, refreshed when expired."""
    if settings.DA_ACCESS_TOKEN and not _expired():
        return settings.DA_ACCESS_TOKEN
    if not settings.DA_REFRESH_TOKEN:
        return settings.DA_ACCESS_TOKEN
    return await refresh_access_token(session)
