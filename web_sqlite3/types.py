from typing import Any, Dict, List, Optional, Union, Tuple
from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class IsolationLevel(Enum):
    DEFERRED = "DEFERRED"
    IMMEDIATE = "IMMEDIATE"
    EXCLUSIVE = "EXCLUSIVE"


class QueryType(Enum):
    SELECT = "SELECT"
    INSERT = "INSERT"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    CREATE = "CREATE"
    DROP = "DROP"
    ALTER = "ALTER"
    OTHER = "OTHER"


@dataclass
class QueryResult:
    rows: List[Dict[str, Any]]
    rowcount: int
    lastrowid: Optional[int]
    execution_time: float
    query_type: QueryType


@dataclass
class ConnectionConfig:
    database: str
    timeout: float = 5.0
    check_same_thread: bool = False
    isolation_level: Optional[IsolationLevel] = None
    cached_statements: int = 128
    uri: bool = False


@dataclass
class PoolConfig:
    min_size: int = 1
    max_size: int = 10
    max_queries: int = 0
    max_idle_time: float = 600.0
    connection_timeout: float = 30.0
    pool_recycle: int = 3600
    echo: bool = False


@dataclass
class ServerConfig:
    host: str = "localhost"
    port: int = 3306
    charset: str = "utf8mb4"
    autocommit: bool = True


Row = Dict[str, Any]
Rows = List[Row]
Parameters = Union[Tuple[Any, ...], Dict[str, Any], None]
