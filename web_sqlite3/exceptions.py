class WebSQLite3Error(Exception):
    pass


class ConnectionError(WebSQLite3Error):
    pass


class PoolExhaustedError(WebSQLite3Error):
    pass


class QueryError(WebSQLite3Error):
    pass


class TransactionError(WebSQLite3Error):
    pass


class ConfigurationError(WebSQLite3Error):
    pass


class TimeoutError(WebSQLite3Error):
    pass


class ValidationError(WebSQLite3Error):
    pass
