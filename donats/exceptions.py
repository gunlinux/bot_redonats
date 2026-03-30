class DomainError(Exception):
    message: str


class CurrencyLoadError(DomainError):
    message = 'CurrencyLoadError'
