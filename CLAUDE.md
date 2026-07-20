# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

SJM Integrator imports XES/CSV customer-journey event logs into an **Event Knowledge Graph (EKG)** following the Customer Journey Modelling Language (CJML) schema. It is a **FastAPI web app** backed by **Apache AGE** (an openCypher graph extension on PostgreSQL), packaged with **Docker**. A Cytoscape.js single-page UI handles import, visualization, querying, and config editing.

## Commands

```bash
# Run everything (DB + app). First run pulls the AGE image and builds the app image.
docker compose up --build          # then open http://localhost:8000
docker compose up -d               # detached
docker compose logs app -f         # follow app logs
docker compose down                # stop (keeps the graph data volume)
docker compose down -v             # stop AND wipe graph data

# Reset the graph without wiping volumes
docker compose exec -T db psql -U postgres -d ekg \
  -c "LOAD 'age'; SET search_path=ag_catalog,public; SELECT drop_graph('ekg_graph', true);"
docker compose restart app         # re-creates the empty graph + labels on startup

# Open a Cypher/psql shell against the graph
docker compose exec db psql -U postgres -d ekg
#   then: LOAD 'age'; SET search_path = ag_catalog, public;
#   SELECT * FROM cypher('ekg_graph', $$ MATCH (t:Touchpoint) RETURN count(t) $$) AS (n agtype);
```

There is no separate lint/test runner. `frontend/` is bind-mounted, so HTML/JS/CSS edits are live on refresh; **Python changes require `docker compose up -d --build`**.

## Architecture

Request flow for an import: **`api/routes_import.py`** reads the upload (CSV: `;` then `,`; XES: validated against `Xes.xsd`, then `pm4py.read_xes`) → **`core/preprocessor.py`** maps raw columns to standard fields per `preprocessing_config.json` → **`core/config_loader.py`** turns `settings.json` into `Class/` mapping objects → **`core/importer.py`** builds the whole graph in pandas and bulk-loads it.

### Bulk-load model (important)
`core/importer.py` is the heart of the system. `build_graph_dataframes()` does **one pass** over the preprocessed log, accumulating all nodes/edges as deduped Python dicts; directly-follows (journey- and entity-based) and planned `Depends` chains are computed in Python. `bulk_load()` then creates everything via **batched `UNWIND ... CREATE`** Cypher. There is no row-by-row MERGE and no post-processing cleanup — the graph is correct by construction.

AGE quirks encoded here:
- Vertices use `CREATE (n:Label) SET n += r` (the directly-unwound map works).
- Edges **cannot** use `SET e += r.props` (AGE rejects nested-map access) — properties are inlined: `CREATE (a)-[:Label {k: r.k}]->(b)`.
- Node `Id` is a stable string we control so edges wire correctly. `Event.Id = "{rowId}_{TimeStampType}"` (synthetic, since multiple timestamps per row become multiple Events). AGE does not enforce vertex uniqueness.

### Graph schema
Vertex labels: `Journey, Log, Touchpoint, Event, Entity, Channel, Experience, Object`.
Edge labels: `Has, Contains, Observe, Sender, Receiver, Corr, Df, Communicated, Rates, Belongs, Depends`. One edge label may span multiple endpoint-type pairs (e.g. `Has` is both Log→Journey and Log→Event), and each node has a single label with semantic distinctions held as properties (`EntityType`, `is_planned`).

### Layers
- `db/age_connection.py` — psycopg2 connection; `cypher(query, columns)` wraps Cypher in `SELECT * FROM cypher('ekg_graph', $$...$$) AS (...)` and parses agtype. Singleton via `get_connection()`. DSN/graph from env (`DB_DSN`, `GRAPH_NAME`).
- `db/agtype.py` — dependency-free `parse_agtype` / `quote_literal` (so `core/` is testable without psycopg2).
- `db/graph_setup.py` — `init_graph()` runs at app startup: `CREATE EXTENSION`, `create_graph`, `create_vlabel`/`create_elabel` (idempotent).
- `api/routes_graph.py` — `/api/graph` (whole-graph sample), `/api/query` (arbitrary AGE Cypher; counts RETURN columns to build the `AS(...)` list), `/api/node/{id}`, `/api/journeys`, `/api/journey/{jid}`, `/api/neighbors/{gid}`. All return Cytoscape.js-shaped `{nodes, edges}` keyed by AGE internal graphid.
- `api/routes_config.py` — GET/PUT the two config files.
- `frontend/` — vanilla JS + Cytoscape.js (dagre layout via jsDelivr, with a built-in fallback). Two independent graph canvases (Graph tab, Query tab), node-properties sidebar, right-click context menu (expand neighbors / hide / focus journey), journey filter dropdown.

### Config is the source of truth
`settings.cjml.json` (read-only canonical CJML field reference), `settings.json` (field→category mapping), `preprocessing_config.json` (raw column→standard field). Editable on disk or via the Config tab; if both exist, import runs without prompts. **`settings_to_mapping_objects()` / `apply_preprocessing()` consume these.** Timestamp fields are auto-detected (`TIMESTAMP_FIELDS`, overridable via a `timestampFields` key in `settings.json`).

### Supporting modules
`Class/` (field/mapping model: `map`, `field`, `touchpoint`, `log`, `objects`), `AutoMapper/autoMapper.py` (Levenshtein field-type detection), `Functions/StringManipulation.py`, `Xes.py`/`Xes.xsd`, `Data/` (sample CSVs + augmentation scripts).

## Gotchas
- **Input must match the config.** `preprocessing_config.json` targets the flattened `*.event`/`*.uuid` CSV export — use `Data/combined-augmented.csv`. `Example.xes` already uses standard column names and needs a different preprocessing config.
- **AGE image tag** form is `release_PG<ver>_<ageversion>` (we pin `release_PG16_1.6.0`); `latest`/`PG17_latest` are unreliable.
- Import **adds** to the graph; reset (above) before re-importing the same data.
