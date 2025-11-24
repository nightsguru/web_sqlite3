<img width="700" height="250" alt="WebSQLITE3" src="https://github.com/user-attachments/assets/e26af95c-f81e-4bec-9519-fcc9c7cc93b4" />

WebSQLITE3 is an enterprise-grade, asynchronous SQLite library for Python. It brings features commonly found in larger database systems like MySQL to SQLite, making it suitable for production-level async applications. It includes connection pooling, a priority-based query queue, semaphore-based concurrency control, and real-time monitoring capabilities.

## Key Features

*   **Asynchronous Core**: Built on top of `aiosqlite` for non-blocking database operations.
*   **Connection Pooling**: Manages a pool of connections to reduce the overhead of establishing connections for each query. Includes configuration for min/max size, connection recycling, and timeouts.
*   **Priority Query Queue**: A `PriorityQueue` schedules queries based on their assigned priority (LOW, NORMAL, HIGH, CRITICAL), ensuring that important operations are executed first.
*   **Concurrency Control**: Uses a semaphore to limit the number of concurrent connections, preventing resource exhaustion.
*   **Robust Transaction Management**: Provides a simple `async with` context manager for handling database transactions safely.
*   **Flexible Configuration**: Configure the client programmatically or by loading settings from a `.json` or `.yaml` file.
*   **Real-time Stats**: A `stats()` method provides insights into the state of the connection pool and query executor, including queue size, active workers, and connection counts.

## Installation

Install the library using pip. It requires `aiosqlite` and `pyyaml`.

```bash
pip install aiosqlite pyyaml
```

## Configuration

You can configure the client by creating a `Config` object, or by loading settings from a file. The library supports both `.json` and `.yaml` formats.

### Example `config.yaml`

```yaml
connection:
  database: "data/production.db"
  timeout: 5.0
  check_same_thread: false
  isolation_level: "DEFERRED" 
  cached_statements: 128
  uri: false

pool:
  min_size: 2
  max_size: 20
  max_queries: 0 # 0 means unlimited
  max_idle_time: 600.0
  connection_timeout: 30.0
  pool_recycle: 3600 # Recycle connections older than 1 hour
  echo: false

server:
  host: "127.0.0.1"
  port: 5084
  charset: "utf8mb4"
  autocommit: true

```

### Loading Configuration

```python
import asyncio
from web_sqlite3 import WebSQLite3Client, Config

# Load from a YAML file
config = Config.from_yaml('path/to/your/config.yaml')
client = WebSQLite3Client(config)

# Or, configure programmatically
from web_sqlite3.types import ConnectionConfig, PoolConfig

client = WebSQLite3Client(
    config=Config(
        connection=ConnectionConfig(database="my_app.db"),
        pool=PoolConfig(min_size=1, max_size=5)
    )
)

async def main():
    await client.connect()
    # ... your code ...
    await client.close()

if __name__ == "__main__":
    asyncio.run(main())
```

## Quick Start

The client is designed to be used as an asynchronous context manager, which handles connection and shutdown automatically.

### Basic Usage

```python
import asyncio
from web_sqlite3 import WebSQLite3Client, Config

async def main():
    config = Config.from_yaml('config.yaml')
    
    async with WebSQLite3Client(config) as client:
        # Create a table
        await client.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                name TEXT,
                email TEXT
            )
        """)
        
        # Insert a user
        await client.execute(
            "INSERT INTO users (name, email) VALUES (?, ?)",
            ("John Doe", "john.doe@example.com")
        )

if __name__ == "__main__":
    asyncio.run(main())
```

### Fetching Data

Use `fetchone()` to get a single record and `fetchall()` to get a list of all matching records.

```python
import asyncio
from web_sqlite3 import WebSQLite3Client, Config

async def main():
    config = Config(connection=ConnectionConfig(database="my_app.db"))
    
    async with WebSQLite3Client(config) as client:
        # Fetch one record
        user = await client.fetchone(
            "SELECT * FROM users WHERE name = ?", ("John Doe",)
        )
        if user:
            print(f"Found user: {user['name']} ({user['email']})")

        # Fetch all records
        all_users = await client.fetchall("SELECT * FROM users")
        print(f"Total users: {len(all_users)}")
        for u in all_users:
            print(f"- ID: {u['id']}, Name: {u['name']}")

if __name__ == "__main__":
    asyncio.run(main())

```

### Using Transactions

To ensure atomicity for a series of operations, use the `transaction()` context manager. It automatically handles `BEGIN`, `COMMIT`, and `ROLLBACK`.

```python
import asyncio
from web_sqlite3 import WebSQLite3Client, Config, QueryError

async def main():
    config = Config(connection=ConnectionConfig(database="my_app.db"))

    async with WebSQLite3Client(config) as client:
        try:
            async with client.transaction() as conn:
                # These operations are part of a single transaction
                await conn.execute(
                    "INSERT INTO users (name, email) VALUES (?, ?)",
                    ("Alice", "alice@web.com")
                )
                await conn.execute(
                    "INSERT INTO users (name, email) VALUES (?, ?)",
                    ("Bob", "bob@web.com")
                )
            print("Transaction committed successfully.")
        except QueryError as e:
            print(f"Transaction failed and was rolled back: {e}")

if __name__ == "__main__":
    asyncio.run(main())
```

### Query Prioritization

You can prioritize important queries to ensure they are executed before lower-priority ones.

```python
import asyncio
from web_sqlite3 import WebSQLite3Client, Config, Priority

async def main():
    config = Config(connection=ConnectionConfig(database="my_app.db"))
    async with WebSQLite3Client(config) as client:
        # Schedule a low-priority logging task
        asyncio.create_task(
            client.execute(
                "INSERT INTO logs (message) VALUES (?)",
                ("User logged in",),
                priority=Priority.LOW
            )
        )

        # Execute a high-priority query to fetch critical data
        admin = await client.fetchone(
            "SELECT * FROM users WHERE id = ?", (1,),
            priority=Priority.CRITICAL
        )
        print(f"Admin user: {admin}")

if __name__ == "__main__":
    asyncio.run(main())
```

### Monitoring and Stats

Get real-time statistics about the connection pool and query executor.

```python
import asyncio
from web_sqlite3 import WebSQLite3Client, Config

async def main():
    config = Config(connection=ConnectionConfig(database="my_app.db"))
    async with WebSQLite3Client(config) as client:
        # ... perform some operations ...
        await client.execute("SELECT 1")

        # Get stats
        stats = client.stats()
        print(stats)
        # {
        #     'initialized': True,
        #     'pool': {'size': 2, 'in_use': 0, 'available': 2, ...},
        #     'executor': {'queue_size': 0, 'workers': 20, 'total_executed': 1, ...},
        #     'config': {...}
        # }

if __name__ == "__main__":
    asyncio.run(main())
```

## API Overview

### `WebSQLite3Client`
The main interface for interacting with the database.
-   `connect()`: Initializes the connection pool and query executor.
-   `close()`: Shuts down workers and closes all connections.
-   `execute(query, params, priority, timeout)`: Executes a general query.
-   `executemany(query, params, priority, timeout)`: Executes a query against a list of parameters.
-   `fetchone(query, params, priority, timeout)`: Fetches the first matching row.
-   `fetchall(query, params, priority, timeout)`: Fetches all matching rows.
-   `transaction()`: An async context manager for atomic transactions.
-   `connection()`: An async context manager to acquire a single connection from the pool.
-   `stats()`: Returns a dictionary of current performance statistics.

### `Priority` Enum
Used to set the priority of a query in the executor queue.
-   `Priority.LOW`
-   `Priority.NORMAL` (default)
-   `Priority.HIGH`
-   `Priority.CRITICAL`

## Exception Handling

The library defines a set of custom exceptions to handle specific error conditions.

-   `WebSQLite3Error`: Base exception for the library.
-   `ConnectionError`: Failed to establish a connection.
-   `PoolExhaustedError`: No connections available in the pool within the timeout.
-   `QueryError`: An error occurred during query execution.
-   `TransactionError`: An issue with a transaction, such as using an uninitialized client.
-   `ConfigurationError`: Invalid or missing configuration file.
-   `TimeoutError`: An operation timed out.

Always wrap database operations in `try...except` blocks to handle potential failures gracefully.

## License

This project is licensed under the MIT License.
