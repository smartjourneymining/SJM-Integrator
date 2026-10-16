"""
psycopg2-based connection to Apache AGE (openCypher on PostgreSQL).

AGE runs Cypher wrapped in SQL:
    SELECT * FROM cypher('<graph>', $$ <cypher> $$) AS (<col> agtype, ...);

Results come back as `agtype` (a JSON superset). This module parses agtype
values into plain Python objects so callers get dicts/lists/scalars.
"""
import os

import psycopg2

# Re-exported for convenience; canonical definitions live in db.agtype.
from db.agtype import parse_agtype, quote_literal  # noqa: F401


class AgeConnection:
    def __init__(self, dsn=None, graph=None):
        self.dsn = dsn or os.environ.get(
            "DB_DSN", "postgresql://postgres:sjm@localhost:5432/ekg"
        )
        self.graph = graph or os.environ.get("GRAPH_NAME", "ekg_graph")
        self.conn = psycopg2.connect(self.dsn)
        self.conn.autocommit = True
        self._prepare_session()

    def _prepare_session(self):
        """Load AGE and set the search path. CREATE EXTENSION is idempotent."""
        with self.conn.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS age;")
            cur.execute("LOAD 'age';")
            cur.execute('SET search_path = ag_catalog, "$user", public;')

    def cypher(self, query, columns="result agtype", graph=None):
        """Run a Cypher query and return a list of dicts of parsed agtype values.

        `columns` is the AS(...) column-definition list. For queries WITH a
        RETURN clause it must match the returned items (e.g. "n agtype, r agtype").
        For write-only queries (no RETURN) a single "result agtype" is fine.
        """
        graph = graph or self.graph
        # Dollar-quote with a custom tag so $$ appearing in data cannot break out.
        sql = f"SELECT * FROM cypher('{graph}', $cyq${query}$cyq$) AS ({columns});"
        with self.conn.cursor() as cur:
            cur.execute(sql)
            if cur.description is None:
                return []
            colnames = [d[0] for d in cur.description]
            rows = cur.fetchall()
        return [
            {colnames[i]: parse_agtype(v) for i, v in enumerate(row)} for row in rows
        ]

    def execute_sql(self, sql, params=None):
        """Run raw SQL (graph/label setup, COPY into staging, indexes)."""
        with self.conn.cursor() as cur:
            cur.execute(sql, params)
            if cur.description is None:
                return []
            return cur.fetchall()

    def close(self):
        if self.conn and not self.conn.closed:
            self.conn.close()


_connection = None


def get_connection():
    """Module-level singleton used by FastAPI routes."""
    global _connection
    if _connection is None:
        _connection = AgeConnection()
    return _connection
