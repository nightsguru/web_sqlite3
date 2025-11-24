import asyncio
from typing import Optional, List, Dict, Any
from contextlib import asynccontextmanager

from .config import Config
from .pool import ConnectionPool
from .executor import QueryExecutor, Priority
from .types import QueryResult, Parameters, Row, Rows
from .connection import Connection
from .exceptions import TransactionError


class WebSQLite3Client:
    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self._pool: Optional[ConnectionPool] = None
        self._executor: Optional[QueryExecutor] = None
        self._initialized = False

    async def connect(self) -> None:
        if self._initialized:
            return

        self._pool = ConnectionPool(
            connection_config=self.config.connection,
            pool_config=self.config.pool
        )
        
        await self._pool.initialize()
        
        self._executor = QueryExecutor(
            pool=self._pool,
            max_queue_size=1000
        )
        
        await self._executor.start(worker_count=self.config.pool.max_size)
        self._initialized = True

    async def close(self) -> None:
        if not self._initialized:
            return

        if self._executor:
            await self._executor.stop()
        
        if self._pool:
            await self._pool.close()
        
        self._initialized = False

    async def execute(
        self,
        query: str,
        parameters: Parameters = None,
        priority: Priority = Priority.NORMAL,
        timeout: Optional[float] = None
    ) -> QueryResult:
        if not self._initialized:
            raise TransactionError("Client not initialized")
        
        return await self._executor.execute(query, parameters, priority, timeout)

    async def executemany(
        self,
        query: str,
        parameters: List[Parameters],
        priority: Priority = Priority.NORMAL,
        timeout: Optional[float] = None
    ) -> QueryResult:
        if not self._initialized:
            raise TransactionError("Client not initialized")
        
        return await self._executor.executemany(query, parameters, priority, timeout)

    async def fetchone(
        self,
        query: str,
        parameters: Parameters = None,
        priority: Priority = Priority.NORMAL,
        timeout: Optional[float] = None
    ) -> Optional[Row]:
        if not self._initialized:
            raise TransactionError("Client not initialized")
        
        return await self._executor.fetchone(query, parameters, priority, timeout)

    async def fetchall(
        self,
        query: str,
        parameters: Parameters = None,
        priority: Priority = Priority.NORMAL,
        timeout: Optional[float] = None
    ) -> Rows:
        if not self._initialized:
            raise TransactionError("Client not initialized")
        
        return await self._executor.fetchall(query, parameters, priority, timeout)

    @asynccontextmanager
    async def transaction(self, timeout: Optional[float] = None):
        if not self._initialized or not self._pool:
            raise TransactionError("Client not initialized")

        conn = await self._pool.acquire(timeout)
        
        try:
            await conn.begin()
            yield conn
            await conn.commit()
        except Exception as e:
            await conn.rollback()
            raise
        finally:
            await self._pool.release(conn)

    @asynccontextmanager
    async def connection(self, timeout: Optional[float] = None):
        if not self._initialized or not self._pool:
            raise TransactionError("Client not initialized")

        async with self._pool.connection(timeout) as conn:
            yield conn

    def stats(self) -> Dict[str, Any]:
        if not self._initialized:
            return {"initialized": False}

        return {
            "initialized": True,
            "pool": self._pool.stats if self._pool else {},
            "executor": self._executor.stats if self._executor else {},
            "config": self.config.to_dict()
        }

    @property
    def is_connected(self) -> bool:
        return self._initialized

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()


class AsyncContextManager:
    def __init__(self, client: WebSQLite3Client):
        self.client = client

    async def __aenter__(self):
        await self.client.connect()
        return self.client

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.close()
