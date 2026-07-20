"""
Graph read endpoints. All return Cytoscape.js-shaped JSON:
  {"nodes": [{"data": {...}}], "edges": [{"data": {...}}]}

AGE vertices/edges come back as agtype dicts with an internal `id` (graphid),
`label`, `properties`, and for edges `start_id`/`end_id`. We key Cytoscape nodes
by that internal id so edges line up.
"""
import re

from fastapi import APIRouter, HTTPException, Query

from db.age_connection import get_connection
from db.agtype import quote_literal
from db.graph_setup import EDGE_LABELS

router = APIRouter(prefix="/api")


def _is_vertex(v):
    return isinstance(v, dict) and "label" in v and "properties" in v and "start_id" not in v


def _is_edge(v):
    return isinstance(v, dict) and "start_id" in v and "end_id" in v


def _vertex_to_cy(v):
    props = v.get("properties", {}) or {}
    return {"data": {"id": str(v.get("id")), "label": v.get("label"), **props}}


def _edge_to_cy(e):
    props = e.get("properties", {}) or {}
    return {"data": {
        "id": "e" + str(e.get("id")),
        "source": str(e.get("start_id")),
        "target": str(e.get("end_id")),
        "label": e.get("label"),
        **props,
    }}


def _rows_to_graph(rows):
    nodes, edges, seen_e = {}, [], set()
    for row in rows:
        for value in row.values():
            if _is_vertex(value):
                nodes.setdefault(value["id"], _vertex_to_cy(value))
            elif _is_edge(value):
                # ensure endpoints exist as (possibly bare) nodes
                if value["id"] not in seen_e:
                    seen_e.add(value["id"])
                    edges.append(_edge_to_cy(value))
    return {"nodes": list(nodes.values()), "edges": edges}


@router.get("/graph")
def get_graph(limit: int = Query(500, ge=1, le=10000)):
    """Whole-graph view: sample each edge label up to a per-label share of `limit`."""
    conn = get_connection()
    per = max(1, limit // max(1, len(EDGE_LABELS)))
    nodes, edges, seen_e = {}, [], set()
    for label in EDGE_LABELS:
        try:
            rows = conn.cypher(
                f"MATCH (a)-[r:{label}]->(b) RETURN a, r, b LIMIT {per}",
                columns="a agtype, r agtype, b agtype",
            )
        except Exception:
            continue
        for row in rows:
            for key in ("a", "b"):
                v = row.get(key)
                if _is_vertex(v):
                    nodes.setdefault(v["id"], _vertex_to_cy(v))
            e = row.get("r")
            if _is_edge(e) and e["id"] not in seen_e:
                seen_e.add(e["id"])
                edges.append(_edge_to_cy(e))
    return {"nodes": list(nodes.values()), "edges": edges, "limited": True}


def _count_return_cols(q):
    """Count top-level comma-separated items in the RETURN clause.

    AGE's SQL wrapper requires an AS(col agtype, ...) list matching the RETURN.
    """
    m = re.search(r"\breturn\b(.*)", q, re.IGNORECASE | re.DOTALL)
    if not m:
        return 1
    clause = re.split(r"\b(order\s+by|limit|skip)\b", m.group(1), flags=re.IGNORECASE)[0]
    depth, cols = 0, 1
    for ch in clause:
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        elif ch == "," and depth == 0:
            cols += 1
    return cols


@router.get("/query")
def run_query(q: str):
    """Run user-supplied AGE Cypher (must include a RETURN) and shape for Cytoscape."""
    conn = get_connection()
    n = _count_return_cols(q)
    columns = ", ".join(f"c{i} agtype" for i in range(n))
    try:
        rows = conn.cypher(q, columns=columns)
    except Exception as exc:
        raise HTTPException(400, f"Query failed: {exc}")
    return _rows_to_graph(rows)


@router.get("/journeys")
def list_journeys():
    """Distinct journey ids, for the journey filter dropdown."""
    conn = get_connection()
    rows = conn.cypher("MATCH (j:Journey) RETURN j.journey", columns="journey agtype")
    vals = {r["journey"] for r in rows if r.get("journey") is not None}
    # Sort numerically when possible, else lexically.
    ordered = sorted(vals, key=lambda x: (len(str(x)), str(x)))
    return {"journeys": ordered}


_JOURNEY_COLS = ["j", "c", "t", "e", "o", "se", "en", "re", "en2", "cm", "ch"]


@router.get("/journey/{jid}")
def journey_subgraph(jid: str):
    """Touchpoints + events + entities + channels for a single journey."""
    conn = get_connection()
    q = (
        "MATCH (j:Journey)-[c:Contains]->(t:Touchpoint) "
        f"WHERE j.journey = {quote_literal(jid)} "
        "OPTIONAL MATCH (e:Event)-[o:Observe]->(t) "
        "OPTIONAL MATCH (t)-[se:Sender]->(en:Entity) "
        "OPTIONAL MATCH (t)-[re:Receiver]->(en2:Entity) "
        "OPTIONAL MATCH (t)-[cm:Communicated]->(ch:Channel) "
        "RETURN " + ", ".join(_JOURNEY_COLS)
    )
    cols = ", ".join(f"{c} agtype" for c in _JOURNEY_COLS)
    try:
        rows = conn.cypher(q, columns=cols)
    except Exception as exc:
        raise HTTPException(400, f"Journey query failed: {exc}")
    return _rows_to_graph(rows)


@router.get("/neighbors/{gid}")
def neighbors(gid: int):
    """1-hop neighborhood of a node identified by its internal graphid."""
    conn = get_connection()
    q = f"MATCH (n)-[r]-(m) WHERE id(n) = {int(gid)} RETURN n, r, m"
    try:
        rows = conn.cypher(q, columns="n agtype, r agtype, m agtype")
    except Exception as exc:
        raise HTTPException(400, f"Neighbor query failed: {exc}")
    return _rows_to_graph(rows)


@router.get("/node/{node_id}")
def get_node(node_id: str):
    """Return all properties of the node whose Id property == node_id."""
    conn = get_connection()
    rows = conn.cypher(
        f"MATCH (n) WHERE n.Id = {quote_literal(node_id)} RETURN n",
        columns="n agtype",
    )
    if not rows:
        raise HTTPException(404, "Node not found")
    v = rows[0]["n"]
    return v.get("properties", v) if isinstance(v, dict) else {"value": v}
