"""
Build the Event Knowledge Graph in two steps:

1. build_graph_dataframes(): one pass over the preprocessed log, accumulating all
   nodes and edges as plain Python structures (deduped by id). Directly-follows
   and entity/planned chains are computed here in Python, not via post-hoc Cypher.
2. bulk_load(): create everything in AGE via batched UNWIND CREATE statements.

The graph is built correctly in one pass — no row-by-row upserts and no
post-processing cleanup passes are needed.
"""
import re

import pandas as pd

from db.agtype import quote_literal

UUID_RE = re.compile(
    r"[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}"
)


def _val(row, key):
    """Return a cleaned cell value, or None for missing/NaN/empty."""
    if key in row:
        v = row[key]
        if not pd.isna(v) and v != "":
            return v
    return None


def _clean_key(k):
    return k.replace("case:", "")


def _collect(row, mapping):
    """All non-null values for a mapping's fields, keyed by cleaned name."""
    out = {}
    for f in mapping.dataFields:
        v = _val(row, f.name)
        if v is not None and not isinstance(v, (list, dict)):
            out[_clean_key(f.name)] = v
    return out


def _is_planned(row):
    ip = _val(row, "case:isPlanned")
    if ip is None:
        return False
    if isinstance(ip, bool):
        return ip
    return str(ip).strip().lower() in ("true", "1", "yes")


def _entity(row, id_field, label_field):
    """(entity_id, entity_type) for a Sender/Receiver, or (None, None)."""
    label_val = _val(row, label_field)
    ent_id = _val(row, id_field) or label_val
    if ent_id is None:
        return None, None
    enduser = _val(row, "case:enduser")
    is_enduser = label_val is not None and (
        enduser == label_val or UUID_RE.search(str(label_val)) is not None
    )
    return ent_id, ("End user" if is_enduser else "Service Provider")


def build_graph_dataframes(df, actor, event, logs, objects_, rating,
                           timestampNames, file_name, time_stamp):
    # Node accumulators: id -> property dict (dedup by id).
    journeys, logs_n, touchpoints, events = {}, {}, {}, {}
    entities, channels, experiences, objects_n = {}, {}, {}, {}

    # Edge groups: name -> {label, from_label, to_label, seen(set), rows(list)}.
    edges = {}

    def add_edge(name, label, fl, tl, src, dst, props=None):
        if src is None or dst is None:
            return
        grp = edges.setdefault(
            name, {"label": label, "from_label": fl, "to_label": tl,
                   "seen": set(), "rows": []}
        )
        key = (src, dst)
        if key in grp["seen"]:
            return
        grp["seen"].add(key)
        clean_props = {_clean_key(k): v for k, v in (props or {}).items()
                       if v is not None}
        grp["rows"].append({"from": src, "to": dst, "props": clean_props})

    log_id = f"{file_name}_{time_stamp}"
    logs_n[log_id] = {"Id": log_id, "fileName": file_name, "timeStamp": int(time_stamp)}

    planned_by_journey = {}  # journey -> [touchpoint_id, ...] in encounter order

    for _, row in df.iterrows():
        journey = _val(row, "case:journey")
        row_id = _val(row, "Id")
        planned = _is_planned(row)

        # --- Journey node (carries all Log-category fields) ---
        if journey is not None and journey not in journeys:
            jp = _collect(row, logs)
            jp.update({"Id": journey, "journey": journey, "EntityType": "Journey"})
            journeys[journey] = jp
        if journey is not None:
            add_edge("Has_Log_Journey", "Has", "Log", "Journey", log_id, journey)

        # --- Event nodes (one per timestamp field, unless planned) ---
        event_ids = []
        if not planned and row_id is not None:
            created = False
            for field_name in timestampNames:
                tv = _val(row, field_name)
                if tv is None:
                    continue
                eid = f"{row_id}_{field_name}"
                ev = _collect(row, event)
                ev.update({"Id": eid, "SourceId": row_id, "journey": journey,
                           "Label": _val(row, "EventType"),
                           "TimeStamp": str(tv), "TimeStampType": field_name})
                events[eid] = ev
                event_ids.append(eid)
                created = True
            if not created:
                eid = str(row_id)
                ev = _collect(row, event)
                ev.update({"Id": eid, "SourceId": row_id, "journey": journey,
                           "Label": _val(row, "EventType")})
                events[eid] = ev
                event_ids.append(eid)

        # --- Touchpoint node (only when initiatorsLabel present) ---
        has_tp = _val(row, "initiatorsLabel") is not None and row_id is not None
        if has_tp and row_id not in touchpoints:
            tp = _collect(row, event)
            tp.update({"Id": row_id, "journey": journey,
                       "EventType": _val(row, "EventType"),
                       "Type": "Touchpoint", "is_planned": planned})
            touchpoints[row_id] = tp
            if planned and journey is not None:
                planned_by_journey.setdefault(journey, []).append(row_id)

        # Observe (Event->Touchpoint) + Contains (Journey->Touchpoint)
        if has_tp:
            for eid in event_ids:
                add_edge("Observe", "Observe", "Event", "Touchpoint", eid, row_id)
            add_edge("Contains", "Contains", "Journey", "Touchpoint", journey, row_id)

        # --- Channel + Communicated ---
        channel = _val(row, "channel")
        if channel is not None:
            channels[channel] = {"Id": channel, "Channel": channel}
            if has_tp:
                add_edge("Communicated", "Communicated", "Touchpoint", "Channel",
                         row_id, channel)

        # --- Entities (Sender always; Receiver only when a channel exists) ---
        sid, stype = _entity(row, "initiatorID", "initiator")
        if sid is not None:
            entities[sid] = {"Id": sid, "EntityType": stype,
                             "name": _val(row, "initiator") or sid}
            if has_tp:
                add_edge("Sender", "Sender", "Touchpoint", "Entity", row_id, sid,
                         {"channel": channel, "Actor": _val(row, "initiator")})
            for eid in event_ids:
                add_edge("Corr", "Corr", "Event", "Entity", eid, sid)

        if channel is not None:
            rid, rtype = _entity(row, "receiversID", "receiver")
            if rid is not None:
                entities[rid] = {"Id": rid, "EntityType": rtype,
                                 "name": _val(row, "receiver") or rid}
                if has_tp:
                    add_edge("Receiver", "Receiver", "Touchpoint", "Entity",
                             row_id, rid,
                             {"channel": channel, "Actor": _val(row, "receiver")})
                for eid in event_ids:
                    add_edge("Corr", "Corr", "Event", "Entity", eid, rid)

        # --- Experience (rating) ---
        if rating.getLength() > 0:
            rprops = _collect(row, rating)
            if rprops:
                exp_id = f"{journey}_{row_id}_exp"
                experiences[exp_id] = {"Id": exp_id, **rprops}
                add_edge("Rates_Journey", "Rates", "Journey", "Experience",
                         journey, exp_id)
                if has_tp:
                    add_edge("Rates_Touchpoint", "Rates", "Touchpoint",
                             "Experience", row_id, exp_id)

        # --- Object (flat only; XES nested-children handling is a TODO) ---
        if objects_.getLength() > 0:
            oprops = _collect(row, objects_)
            if oprops:
                obj_id = f"{journey}_{row_id}_obj"
                objects_n[obj_id] = {"Id": obj_id, **oprops}
                if has_tp:
                    add_edge("Belongs", "Belongs", "Touchpoint", "Object",
                             row_id, obj_id)

    # --- Has (Log->Event) for every event ---
    for eid in events:
        add_edge("Has_Log_Event", "Has", "Log", "Event", log_id, eid)

    # --- Directly-follows (journey-based) over events ---
    _add_df_chains(
        edges, events,
        group_by=lambda e: e.get("journey"),
        entity_type=lambda key: "Journey",
        name="Df_Journey",
    )

    # --- Directly-follows (entity-based): chain events sharing a Corr entity ---
    corr = edges.get("Corr")
    if corr:
        # entity id -> [event ids correlated to it]
        entity_events = {}
        for r in corr["rows"]:
            entity_events.setdefault(r["to"], []).append(r["from"])
        for ent_id, ev_ids in entity_events.items():
            etype = entities.get(ent_id, {}).get("EntityType", "Entity")
            ordered = sorted(set(ev_ids), key=lambda e: _sort_key(events.get(e, {})))
            for a, b in zip(ordered, ordered[1:]):
                add_edge("Df_Entity", "Df", "Event", "Event", a, b,
                         {"EntityType": etype})

    # --- Planned Depends chains (per journey, encounter order) ---
    for journey, tp_ids in planned_by_journey.items():
        for a, b in zip(tp_ids, tp_ids[1:]):
            add_edge("Depends", "Depends", "Touchpoint", "Touchpoint", b, a)

    nodes = {
        "Journey": list(journeys.values()),
        "Log": list(logs_n.values()),
        "Touchpoint": list(touchpoints.values()),
        "Event": list(events.values()),
        "Entity": list(entities.values()),
        "Channel": list(channels.values()),
        "Experience": list(experiences.values()),
        "Object": list(objects_n.values()),
    }
    # Strip the internal dedup helper before returning edges.
    out_edges = {name: {k: g[k] for k in ("label", "from_label", "to_label", "rows")}
                 for name, g in edges.items()}
    return {"nodes": nodes, "edges": out_edges}


def _sort_key(ev):
    return (str(ev.get("TimeStamp") or ""), str(ev.get("Id") or ""))


def _add_df_chains(edges, events, group_by, entity_type, name):
    """Generic directly-follows: group events, sort, link consecutive pairs."""
    groups = {}
    for eid, ev in events.items():
        key = group_by(ev)
        if key is None:
            continue
        groups.setdefault(key, []).append(eid)
    grp = edges.setdefault(
        name, {"label": "Df", "from_label": "Event", "to_label": "Event",
               "seen": set(), "rows": []}
    )
    for key, ev_ids in groups.items():
        ordered = sorted(ev_ids, key=lambda e: _sort_key(events[e]))
        for a, b in zip(ordered, ordered[1:]):
            if (a, b) in grp["seen"]:
                continue
            grp["seen"].add((a, b))
            grp["rows"].append(
                {"from": a, "to": b, "props": {"EntityType": entity_type(key)}}
            )


# --------------------------------------------------------------------------- #
# Bulk load via batched UNWIND CREATE
# --------------------------------------------------------------------------- #

def _chunks(seq, size=500):
    for i in range(0, len(seq), size):
        yield seq[i:i + size]


def _map_literal(d):
    return "{" + ", ".join(f"`{k}`: {quote_literal(v)}" for k, v in d.items()) + "}"


def _nodes_literal(batch):
    return "[" + ", ".join(_map_literal(d) for d in batch) + "]"


def _edges_literal(batch, prop_keys):
    # Flat maps: src/dst plus each property as a top-level key. AGE 1.6.0 does not
    # accept `SET e += r.props` (nested-map access), so we inline props in CREATE
    # and reference them as flat r.`key` scalars.
    parts = []
    for r in batch:
        fields = [f"src: {quote_literal(r['from'])}", f"dst: {quote_literal(r['to'])}"]
        for k in prop_keys:
            fields.append(f"`{k}`: {quote_literal(r['props'].get(k))}")
        parts.append("{" + ", ".join(fields) + "}")
    return "[" + ", ".join(parts) + "]"


def bulk_load(conn, graph_data, batch_size=500):
    """Create all nodes (before any edges), then all edges. Returns counts."""
    counts = {}

    for label, node_list in graph_data["nodes"].items():
        if not node_list:
            continue
        for batch in _chunks(node_list, batch_size):
            q = f"UNWIND {_nodes_literal(batch)} AS r CREATE (n:{label}) SET n += r"
            conn.cypher(q, columns="result agtype")
        counts[label] = len(node_list)

    for name, grp in graph_data["edges"].items():
        rows = grp["rows"]
        if not rows:
            continue
        label, fl, tl = grp["label"], grp["from_label"], grp["to_label"]
        prop_keys = sorted({k for r in rows for k in r["props"]})
        prop_clause = ""
        if prop_keys:
            prop_clause = " {" + ", ".join(f"`{k}`: r.`{k}`" for k in prop_keys) + "}"
        for batch in _chunks(rows, batch_size):
            q = (
                f"UNWIND {_edges_literal(batch, prop_keys)} AS r "
                f"MATCH (a:{fl} {{Id: r.src}}), (b:{tl} {{Id: r.dst}}) "
                f"CREATE (a)-[:{label}{prop_clause}]->(b)"
            )
            conn.cypher(q, columns="result agtype")
        counts[f"{label}:{name}"] = len(rows)

    return counts
