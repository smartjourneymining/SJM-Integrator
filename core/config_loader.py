"""
Load the two config files that drive a headless import and convert them into the
Class/ mapping objects the importer expects.

- settings.json          : field -> category mapping (Actor/Event/Log/Rating/Object)
- preprocessing_config.json : raw CSV column -> standard field mapping

Both are the source of truth; the web UI is only an editor for them.
"""
import json
import os

from Class.map import field
from Class.event import touchpoint
from Class.log import log
from Class.objects import objects

SETTINGS_PATH = "settings.json"
PREPROCESSING_PATH = "preprocessing_config.json"
CJML_REFERENCE_PATH = "settings.cjml.json"

# Canonical timestamp fields (from settings.cjml.json Event section).
# Overridable via a "timestampFields" key in settings.json.
TIMESTAMP_FIELDS = [
    "timestamp",
    "dateCompleted",
    "dateStart",
    "dateOriginated",
    "dateReceiver",
    "dateConsumed",
    "Deltadate",
]


def load_settings(path=SETTINGS_PATH):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_preprocessing_config(path=PREPROCESSING_PATH):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def configs_are_complete():
    """True if both config files exist and parse — enables headless import."""
    for path in (SETTINGS_PATH, PREPROCESSING_PATH):
        if not os.path.exists(path):
            return False
        try:
            with open(path, "r", encoding="utf-8") as f:
                json.load(f)
        except (json.JSONDecodeError, OSError):
            return False
    return True


def _field_from_dict(d):
    """Build a Class.map.field from a settings dict, tolerating both the
    settings.json form (entity_type) and the settings.cjml.json form (actor_type)."""
    return field(
        name=d["name"],
        type_map=d.get("type_map", ""),
        identifier=d.get("identifier", 0),
        foreign_key=d.get("foreign_key", 0),
        to_type=d.get("to_type", ""),
        entity_type=d.get("entity_type", d.get("actor_type", "")),
    )


def settings_to_mapping_objects(settings):
    """Convert a settings dict into (actor, event, logs, objects_, rating)."""
    entity_key = "Entity" if "Entity" in settings else "Actor"
    actor = touchpoint([_field_from_dict(e) for e in settings.get(entity_key, [])])
    event = touchpoint([_field_from_dict(e) for e in settings.get("Event", [])])
    logs = log([_field_from_dict(e) for e in settings.get("Log", [])])
    rating = touchpoint([_field_from_dict(e) for e in settings.get("Rating", [])])
    objects_ = objects([_field_from_dict(e) for e in settings.get("Object", [])])
    return actor, event, logs, objects_, rating


def get_timestamp_fields(settings, event_mapping):
    """Timestamp field names present in the Event mapping.

    Honors an optional settings["timestampFields"] override, else falls back to
    the canonical TIMESTAMP_FIELDS constant.
    """
    candidates = settings.get("timestampFields") or TIMESTAMP_FIELDS
    event_names = {f.name for f in event_mapping.dataFields}
    return [name for name in candidates if name in event_names]
