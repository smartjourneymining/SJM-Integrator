"""Config endpoints: read/write settings.json and preprocessing_config.json."""
import json
import os
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/api")

_FILES = {"settings": "settings.json", "preprocessing": "preprocessing_config.json"}
_CJML = "settings.cjml.json"


@router.get("/schema")
def get_schema():
    """Canonical CJML standard fields + their default categorization, plus the
    option lists the interactive editor needs."""
    cjml = {}
    if os.path.exists(_CJML):
        with open(_CJML, encoding="utf-8") as f:
            cjml = json.load(f)

    defaults = {}
    for key, items in cjml.items():
        for fd in items:
            name = fd.get("name")
            if not name:
                continue
            defaults[name] = {
                "category": fd.get("type_map", "Entity" if key == "Entity" else key),
                "identifier": fd.get("identifier", 0),
                "foreign_key": fd.get("foreign_key", 0),
                "to_type": fd.get("to_type", ""),
                "entity_type": fd.get("entity_type", fd.get("actor_type", "")),
            }

    return {
        "standard_fields": sorted(defaults.keys()),
        "defaults": defaults,
        "categories": ["Entity", "Event", "Log", "Rating", "Object"],
        "entity_types": ["Sender", "Receiver", "Both"],
        "generation_types": [
            "Auto-increment (numeric)",
            "Auto-increment (ID1, ID2, ...)",
            "UUID",
            "Row number",
        ],
    }


@router.get("/config")
def get_config():
    out = {}
    for key, path in _FILES.items():
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                out[key] = json.load(f)
        else:
            out[key] = None
    return out


class ConfigPayload(BaseModel):
    settings: Optional[dict] = None
    preprocessing: Optional[dict] = None


@router.put("/config")
def put_config(payload: ConfigPayload):
    if payload.settings is not None:
        with open(_FILES["settings"], "w", encoding="utf-8") as f:
            json.dump(payload.settings, f, indent=4, ensure_ascii=False)
    if payload.preprocessing is not None:
        with open(_FILES["preprocessing"], "w", encoding="utf-8") as f:
            json.dump(payload.preprocessing, f, indent=4, ensure_ascii=False)
    return {"status": "ok"}
