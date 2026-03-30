import pytest

from donats.utils import get_currencies
from donats.exceptions import CurrencyLoadError


async def test_bad_currencies():
    with pytest.raises(CurrencyLoadError):
        assert get_currencies('wrong_file.json') is None

    with pytest.raises(CurrencyLoadError):
        assert get_currencies('tests/data/bad_currencies.json') is None


async def test_load_currencies():
    currencies = get_currencies('tests/data/currencies.json')
    assert currencies is not None
    for value in currencies.values():
        assert isinstance(value, float)
