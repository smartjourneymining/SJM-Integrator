# SJM Integrator [![DOI](https://zenodo.org/badge/728133494.svg)](https://zenodo.org/doi/10.5281/zenodo.10307556)

SJM Integrator imports XES/CSV customer-journey event logs into an **Event Knowledge Graph (EKG)** following the Customer Journey Modelling Language (CJML) format. It is a self-contained web application: a **FastAPI** backend over **Apache AGE** (an openCypher graph database that runs as a PostgreSQL extension), with a browser-based UI for importing, visualizing, and querying the graph. Everything runs via **Docker** — no separate database install or credentials needed.

## Requirements

- [Docker](https://docs.docker.com/get-docker/) with Docker Compose (Docker Desktop, or Docker Engine + the `compose` plugin).

That's it — Python, PostgreSQL, and Apache AGE all run inside containers.

## Running

```bash
docker compose up --build
```

The first run pulls the Apache AGE database image and builds the app image (a few minutes). When it's up, open:

```
http://localhost:8000
```

Common commands:

```bash
docker compose up -d            # run in the background
docker compose logs app -f      # follow application logs
docker compose down             # stop (graph data is kept)
docker compose down -v          # stop and wipe all graph data
```

## Use

The web UI has four tabs:

1. **Config** — view/edit `settings.json` (field → category mapping) and `preprocessing_config.json` (raw column → standard field). These are the source of truth for imports and can also be edited directly on disk. Click **Reload** to load them.
2. **Import** — upload a `.csv` or `.xes` file and click **Import**. The graph is built and a summary of created nodes/edges is shown.
   - Use a file whose columns match `preprocessing_config.json`. The included config matches **`Data/combined-augmented.csv`**.
   - Importing *adds* to the graph; reset first (below) for a clean run.
3. **Graph** — click **Load Graph** to view the EKG. Filter to a single journey with the **Journey** dropdown + **Show Journey**. **Right-click any node** to expand its neighbors, focus its journey, hide it, or view its properties.
4. **Query** — run AGE/openCypher queries (must include a `RETURN`) or pick a preset; results render on the Query tab's own canvas.

### Reset the graph

```bash
docker compose exec -T db psql -U postgres -d ekg \
  -c "LOAD 'age'; SET search_path=ag_catalog,public; SELECT drop_graph('ekg_graph', true);"
docker compose restart app
```

## Querying directly (optional)

```bash
docker compose exec db psql -U postgres -d ekg
```
```sql
LOAD 'age'; SET search_path = ag_catalog, public;
SELECT * FROM cypher('ekg_graph', $$
  MATCH (j:Journey)-[:Contains]->(t:Touchpoint) RETURN j.journey, count(t)
$$) AS (journey agtype, touchpoints agtype);
```

## Development

`frontend/` is bind-mounted into the app container, so HTML/JS/CSS edits are live on browser refresh. Python changes require a rebuild:

```bash
docker compose up -d --build
```

See `CLAUDE.md` for the architecture overview.
