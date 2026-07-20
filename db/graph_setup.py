"""
One-time Apache AGE graph + label setup.

AGE vertices/edges each carry exactly one label, and labels must exist before
data is created against them. There is no fixed-column schema: properties are
stored as agtype/JSON, and one edge label may connect different vertex-type
pairs (so `:Has` works for both Log->Journey and Log->Event).
"""
import psycopg2

# Vertex labels. Each node has exactly one label; semantic distinctions are
# properties (e.g. Journey carries EntityType, Touchpoint carries is_planned).
VERTEX_LABELS = [
    "Journey",
    "Log",
    "Touchpoint",
    "Event",
    "Entity",
    "Channel",
    "Experience",
    "Object",
]

# Edge labels. One label may span multiple endpoint-type pairs in AGE.
EDGE_LABELS = [
    "Has",          # Log->Journey, Log->Event
    "Contains",     # Journey->Touchpoint
    "Observe",      # Event->Touchpoint
    "Sender",       # Touchpoint->Entity
    "Receiver",     # Touchpoint->Entity
    "Corr",         # Event->Entity
    "Df",           # Event->Event (directly-follows)
    "Communicated", # Touchpoint->Channel
    "Rates",        # Journey->Experience, Touchpoint->Experience
    "Belongs",      # Touchpoint->Object
    "Depends",      # Touchpoint->Touchpoint (planned)
]


def _try(conn, sql, ignore="already exists"):
    """Run a setup statement, tolerating 'already exists' errors (idempotent).

    The connection is autocommit, so each statement is its own transaction and a
    failure here does not poison subsequent statements.
    """
    try:
        conn.execute_sql(sql)
    except psycopg2.Error as exc:
        msg = str(exc)
        if ignore and ignore in msg:
            return
        # Re-raise anything that is not the expected idempotency case.
        raise


def init_graph(conn):
    """Create the graph and all vertex/edge labels if they do not yet exist."""
    graph = conn.graph

    # Extension is also ensured on connect; harmless to repeat.
    _try(conn, "CREATE EXTENSION IF NOT EXISTS age;", ignore=None)

    # Create the graph only if absent (create_graph errors if it exists).
    rows = conn.execute_sql(
        "SELECT count(*) FROM ag_catalog.ag_graph WHERE name = %s;", (graph,)
    )
    if rows and rows[0][0] == 0:
        _try(conn, f"SELECT create_graph('{graph}');")

    for label in VERTEX_LABELS:
        _try(conn, f"SELECT create_vlabel('{graph}', '{label}');")

    for label in EDGE_LABELS:
        _try(conn, f"SELECT create_elabel('{graph}', '{label}');")
