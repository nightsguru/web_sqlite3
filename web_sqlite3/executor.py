import asyncio
from typing import Optional, List, Callable, Any
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from .types import QueryResult, Parameters, Row, Rows
from .pool import ConnectionPool
from .exceptions import QueryError


class Priority(Enum):
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


@dataclass
class QueryTask:
    query: str
    parameters: Parameters
    priority: Priority
    created_at: datetime
    future: asyncio.Future
    many: bool = False
    batch_parameters: Optional[List[Parameters]] = None


class QueryExecutor:
    def __init__(self, pool: ConnectionPool, max_queue_size: int = 1000):
        self.pool = pool
        self.max_queue_size = max_queue_size
        
        self._queue: asyncio.PriorityQueue = asyncio.PriorityQueue(maxsize=max_queue_size)
        self._workers: List[asyncio.Task] = []
        self._running = False
        self._worker_count = 5
        
        self._total_executed = 0
        self._total_failed = 0
        self._lock = asyncio.Lock()
        self._task_counter = 0

    async def start(self, worker_count: int = 5) -> None:
        if self._running:
            return

        self._worker_count = worker_count
        self._running = True
        
        for _ in range(worker_count):
            worker = asyncio.create_task(self._worker())
            self._workers.append(worker)

    async def stop(self) -> None:
        self._running = False
        
        for worker in self._workers:
            worker.cancel()
        
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()

    async def _worker(self) -> None:
        while self._running:
            try:
                priority_value, counter, task = await asyncio.wait_for(
                    self._queue.get(),
                    timeout=0.1
                )
                
                await self._execute_task(task)
                self._queue.task_done()
                
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                async with self._lock:
                    self._total_failed += 1

    async def _execute_task(self, task: QueryTask) -> None:
        try:
            async with self.pool.connection() as conn:
                if task.many and task.batch_parameters:
                    result = await conn.executemany(task.query, task.batch_parameters)
                else:
                    result = await conn.execute(task.query, task.parameters)
                
                task.future.set_result(result)
                
                async with self._lock:
                    self._total_executed += 1
                    
        except Exception as e:
            if not task.future.done():
                task.future.set_exception(e)
            
            async with self._lock:
                self._total_failed += 1

    async def execute(
        self,
        query: str,
        parameters: Parameters = None,
        priority: Priority = Priority.NORMAL,
        timeout: Optional[float] = None
    ) -> QueryResult:
        future: asyncio.Future = asyncio.Future()
        
        task = QueryTask(
            query=query,
            parameters=parameters,
            priority=priority,
            created_at=datetime.now(),
            future=future
        )
        
        priority_value = -priority.value
        
        async with self._lock:
            counter = self._task_counter
            self._task_counter += 1
        
        try:
            await asyncio.wait_for(
                self._queue.put((priority_value, counter, task)),
                timeout=1.0
            )
        except asyncio.TimeoutError:
            raise QueryError("Query queue is full")
        
        try:
            if timeout:
                result = await asyncio.wait_for(future, timeout=timeout)
            else:
                result = await future
            return result
        except asyncio.TimeoutError:
            raise QueryError(f"Query execution timeout after {timeout}s")

    async def executemany(
        self,
        query: str,
        parameters: List[Parameters],
        priority: Priority = Priority.NORMAL,
        timeout: Optional[float] = None
    ) -> QueryResult:
        future: asyncio.Future = asyncio.Future()
        
        task = QueryTask(
            query=query,
            parameters=None,
            priority=priority,
            created_at=datetime.now(),
            future=future,
            many=True,
            batch_parameters=parameters
        )
        
        priority_value = -priority.value
        
        async with self._lock:
            counter = self._task_counter
            self._task_counter += 1
        
        try:
            await asyncio.wait_for(
                self._queue.put((priority_value, counter, task)),
                timeout=1.0
            )
        except asyncio.TimeoutError:
            raise QueryError("Query queue is full")
        
        try:
            if timeout:
                result = await asyncio.wait_for(future, timeout=timeout)
            else:
                result = await future
            return result
        except asyncio.TimeoutError:
            raise QueryError(f"Batch execution timeout after {timeout}s")

    async def fetchone(
        self,
        query: str,
        parameters: Parameters = None,
        priority: Priority = Priority.NORMAL,
        timeout: Optional[float] = None
    ) -> Optional[Row]:
        result = await self.execute(query, parameters, priority, timeout)
        return result.rows[0] if result.rows else None

    async def fetchall(
        self,
        query: str,
        parameters: Parameters = None,
        priority: Priority = Priority.NORMAL,
        timeout: Optional[float] = None
    ) -> Rows:
        result = await self.execute(query, parameters, priority, timeout)
        return result.rows

    @property
    def queue_size(self) -> int:
        return self._queue.qsize()

    @property
    def stats(self) -> dict:
        return {
            "queue_size": self._queue.qsize(),
            "workers": len(self._workers),
            "total_executed": self._total_executed,
            "total_failed": self._total_failed,
            "running": self._running
        }

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.stop()