import aiosqlite
import asyncio
from typing import Optional, List, Any
from datetime import datetime

from .types import ConnectionConfig, QueryResult, QueryType, Parameters, Row, Rows
from .exceptions import ConnectionError, QueryError


class Connection:
    def __init__(self, config: ConnectionConfig):
        self.config = config
        self._conn: Optional[aiosqlite.Connection] = None
        self._created_at: Optional[datetime] = None
        self._query_count: int = 0
        self._in_transaction: bool = False
        self._lock = asyncio.Lock()

    async def connect(self) -> None:
        if self._conn is not None:
            return

        try:
            isolation_level = None
            if self.config.isolation_level:
                isolation_level = self.config.isolation_level.value

            self._conn = await aiosqlite.connect(
                database=self.config.database,
                timeout=self.config.timeout,
                check_same_thread=self.config.check_same_thread,
                isolation_level=isolation_level,
                cached_statements=self.config.cached_statements,
                uri=self.config.uri
            )
            self._conn.row_factory = aiosqlite.Row
            self._created_at = datetime.now()
        except Exception as e:
            raise ConnectionError(f"Failed to connect to database: {e}")

    async def close(self) -> None:
        if self._conn is not None:
            await self._conn.close()
            self._conn = None
            self._created_at = None

    async def execute(
        self,
        query: str,
        parameters: Parameters = None
    ) -> QueryResult:
        if self._conn is None:
            raise ConnectionError("Connection not established")

        async with self._lock:
            start_time = datetime.now()
            query_type = self._detect_query_type(query)

            try:
                cursor = await self._conn.execute(query, parameters or ())
                
                if query_type == QueryType.SELECT:
                    rows = await cursor.fetchall()
                    result_rows = [dict(row) for row in rows]
                else:
                    result_rows = []

                await cursor.close()

                if not self._in_transaction:
                    await self._conn.commit()

                execution_time = (datetime.now() - start_time).total_seconds()
                self._query_count += 1

                return QueryResult(
                    rows=result_rows,
                    rowcount=cursor.rowcount,
                    lastrowid=cursor.lastrowid,
                    execution_time=execution_time,
                    query_type=query_type
                )
            except Exception as e:
                if not self._in_transaction:
                    await self._conn.rollback()
                raise QueryError(f"Query execution failed: {e}")

    async def executemany(
        self,
        query: str,
        parameters: List[Parameters]
    ) -> QueryResult:
        if self._conn is None:
            raise ConnectionError("Connection not established")

        async with self._lock:
            start_time = datetime.now()
            query_type = self._detect_query_type(query)

            try:
                cursor = await self._conn.executemany(query, parameters)
                
                if not self._in_transaction:
                    await self._conn.commit()

                execution_time = (datetime.now() - start_time).total_seconds()
                self._query_count += 1

                return QueryResult(
                    rows=[],
                    rowcount=cursor.rowcount,
                    lastrowid=cursor.lastrowid,
                    execution_time=execution_time,
                    query_type=query_type
                )
            except Exception as e:
                if not self._in_transaction:
                    await self._conn.rollback()
                raise QueryError(f"Batch execution failed: {e}")

    async def fetchone(self, query: str, parameters: Parameters = None) -> Optional[Row]:
        result = await self.execute(query, parameters)
        return result.rows[0] if result.rows else None

    async def fetchall(self, query: str, parameters: Parameters = None) -> Rows:
        result = await self.execute(query, parameters)
        return result.rows

    async def begin(self) -> None:
        if self._conn is None:
            raise ConnectionError("Connection not established")
        if self._in_transaction:
            return
        
        await self._conn.execute("BEGIN")
        self._in_transaction = True

    async def commit(self) -> None:
        if self._conn is None:
            raise ConnectionError("Connection not established")
        if not self._in_transaction:
            return
        
        await self._conn.commit()
        self._in_transaction = False

    async def rollback(self) -> None:
        if self._conn is None:
            raise ConnectionError("Connection not established")
        if not self._in_transaction:
            return
        
        await self._conn.rollback()
        self._in_transaction = False

    @staticmethod
    def _detect_query_type(query: str) -> QueryType:
        normalized = query.strip().upper()
        
        if normalized.startswith("SELECT"):
            return QueryType.SELECT
        elif normalized.startswith("INSERT"):
            return QueryType.INSERT
        elif normalized.startswith("UPDATE"):
            return QueryType.UPDATE
        elif normalized.startswith("DELETE"):
            return QueryType.DELETE
        elif normalized.startswith("CREATE"):
            return QueryType.CREATE
        elif normalized.startswith("DROP"):
            return QueryType.DROP
        elif normalized.startswith("ALTER"):
            return QueryType.ALTER
        else:
            return QueryType.OTHER

    @property
    def is_connected(self) -> bool:
        return self._conn is not None

    @property
    def query_count(self) -> int:
        return self._query_count

    @property
    def created_at(self) -> Optional[datetime]:
        return self._created_at

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
