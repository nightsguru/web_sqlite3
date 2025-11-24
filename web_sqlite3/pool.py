import asyncio
from typing import Optional, List, Set
from datetime import datetime, timedelta
from contextlib import asynccontextmanager

from .types import ConnectionConfig, PoolConfig
from .connection import Connection
from .exceptions import PoolExhaustedError, TimeoutError


class ConnectionPool:
    def __init__(self, connection_config: ConnectionConfig, pool_config: PoolConfig):
        self.connection_config = connection_config
        self.pool_config = pool_config
        
        self._available: asyncio.Queue[Connection] = asyncio.Queue()
        self._in_use: Set[Connection] = set()
        self._all_connections: Set[Connection] = set()
        
        self._semaphore = asyncio.Semaphore(pool_config.max_size)
        self._size = 0
        self._closed = False
        self._lock = asyncio.Lock()
        
        self._total_acquired = 0
        self._total_released = 0

    async def initialize(self) -> None:
        for _ in range(self.pool_config.min_size):
            conn = await self._create_connection()
            await self._available.put(conn)

    async def _create_connection(self) -> Connection:
        conn = Connection(self.connection_config)
        await conn.connect()
        
        async with self._lock:
            self._all_connections.add(conn)
            self._size += 1
        
        return conn

    async def acquire(self, timeout: Optional[float] = None) -> Connection:
        if self._closed:
            raise PoolExhaustedError("Pool is closed")

        timeout = timeout or self.pool_config.connection_timeout
        
        try:
            await asyncio.wait_for(
                self._semaphore.acquire(),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            raise TimeoutError(f"Timeout acquiring connection after {timeout}s")

        conn: Optional[Connection] = None

        try:
            conn = await asyncio.wait_for(
                self._available.get(),
                timeout=0.1
            )
        except asyncio.TimeoutError:
            if self._size < self.pool_config.max_size:
                conn = await self._create_connection()
            else:
                try:
                    conn = await asyncio.wait_for(
                        self._available.get(),
                        timeout=timeout
                    )
                except asyncio.TimeoutError:
                    self._semaphore.release()
                    raise PoolExhaustedError("All connections are in use")

        if conn is None:
            self._semaphore.release()
            raise PoolExhaustedError("Failed to acquire connection")

        if not conn.is_connected:
            await conn.connect()

        if self._should_recycle(conn):
            await conn.close()
            conn = await self._create_connection()

        async with self._lock:
            self._in_use.add(conn)
            self._total_acquired += 1

        return conn

    async def release(self, conn: Connection) -> None:
        if conn not in self._in_use:
            return

        async with self._lock:
            self._in_use.discard(conn)
            self._total_released += 1

        if self.pool_config.max_queries > 0 and conn.query_count >= self.pool_config.max_queries:
            await self._remove_connection(conn)
        else:
            await self._available.put(conn)

        self._semaphore.release()

    async def _remove_connection(self, conn: Connection) -> None:
        async with self._lock:
            if conn in self._all_connections:
                self._all_connections.discard(conn)
                self._size -= 1

        await conn.close()

    def _should_recycle(self, conn: Connection) -> bool:
        if self.pool_config.pool_recycle <= 0:
            return False
        
        if conn.created_at is None:
            return False

        age = (datetime.now() - conn.created_at).total_seconds()
        return age > self.pool_config.pool_recycle

    async def close(self) -> None:
        self._closed = True

        async with self._lock:
            all_conns = list(self._all_connections)

        for conn in all_conns:
            await conn.close()

        async with self._lock:
            self._all_connections.clear()
            self._in_use.clear()
            self._size = 0

        while not self._available.empty():
            try:
                self._available.get_nowait()
            except asyncio.QueueEmpty:
                break

    @asynccontextmanager
    async def connection(self, timeout: Optional[float] = None):
        conn = await self.acquire(timeout)
        try:
            yield conn
        finally:
            await self.release(conn)

    @property
    def size(self) -> int:
        return self._size

    @property
    def in_use_count(self) -> int:
        return len(self._in_use)

    @property
    def available_count(self) -> int:
        return self._available.qsize()

    @property
    def stats(self) -> dict:
        return {
            "size": self._size,
            "in_use": len(self._in_use),
            "available": self._available.qsize(),
            "total_acquired": self._total_acquired,
            "total_released": self._total_released,
            "closed": self._closed
        }

    async def __aenter__(self):
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
