import json
import yaml
from pathlib import Path
from typing import Optional, Dict, Any

from .types import ConnectionConfig, PoolConfig, ServerConfig, IsolationLevel
from .exceptions import ConfigurationError


class Config:
    def __init__(
        self,
        connection: Optional[ConnectionConfig] = None,
        pool: Optional[PoolConfig] = None,
        server: Optional[ServerConfig] = None
    ):
        self.connection = connection or ConnectionConfig(database=":memory:")
        self.pool = pool or PoolConfig()
        self.server = server or ServerConfig()

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Config":
        connection_data = data.get("connection", {})
        pool_data = data.get("pool", {})
        server_data = data.get("server", {})

        if "isolation_level" in connection_data:
            isolation = connection_data["isolation_level"]
            if isinstance(isolation, str):
                connection_data["isolation_level"] = IsolationLevel[isolation.upper()]

        connection = ConnectionConfig(**connection_data)
        pool = PoolConfig(**pool_data)
        server = ServerConfig(**server_data)

        return cls(connection=connection, pool=pool, server=server)

    @classmethod
    def from_json(cls, path: str) -> "Config":
        file_path = Path(path)
        if not file_path.exists():
            raise ConfigurationError(f"Configuration file not found: {path}")

        try:
            with open(file_path, "r") as f:
                data = json.load(f)
            return cls.from_dict(data)
        except json.JSONDecodeError as e:
            raise ConfigurationError(f"Invalid JSON configuration: {e}")

    @classmethod
    def from_yaml(cls, path: str) -> "Config":
        file_path = Path(path)
        if not file_path.exists():
            raise ConfigurationError(f"Configuration file not found: {path}")

        try:
            with open(file_path, "r") as f:
                data = yaml.safe_load(f)
            return cls.from_dict(data)
        except yaml.YAMLError as e:
            raise ConfigurationError(f"Invalid YAML configuration: {e}")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "connection": {
                "database": self.connection.database,
                "timeout": self.connection.timeout,
                "check_same_thread": self.connection.check_same_thread,
                "isolation_level": self.connection.isolation_level.value if self.connection.isolation_level else None,
                "cached_statements": self.connection.cached_statements,
                "uri": self.connection.uri
            },
            "pool": {
                "min_size": self.pool.min_size,
                "max_size": self.pool.max_size,
                "max_queries": self.pool.max_queries,
                "max_idle_time": self.pool.max_idle_time,
                "connection_timeout": self.pool.connection_timeout,
                "pool_recycle": self.pool.pool_recycle,
                "echo": self.pool.echo
            },
            "server": {
                "host": self.server.host,
                "port": self.server.port,
                "charset": self.server.charset,
                "autocommit": self.server.autocommit
            }
        }
