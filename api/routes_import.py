"""POST /api/import — upload a CSV/XES file and load it into the EKG."""
import os
import tempfile
import time

import pandas as pd
import pm4py
import xmlschema
from fastapi import APIRouter, File, HTTPException, UploadFile

from core import config_loader, importer, preprocessor
from db.age_connection import get_connection

router = APIRouter(prefix="/api")

XSD_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "Xes.xsd")


def _read_csv(path):
    """Read a CSV trying ';' then ',' (European files), stripping BOM headers."""
    for sep in (";", ","):
        try:
            df = pd.read_csv(path, sep=sep, encoding="utf-8-sig")
            df.columns = df.columns.str.replace("﻿", "", regex=False)
            if len(df.columns) > 1:
                return df
        except Exception:
            continue
    raise HTTPException(400, "Failed to read CSV file")


@router.post("/import")
async def import_file(file: UploadFile = File(...)):
    if not config_loader.configs_are_complete():
        raise HTTPException(
            400, "Missing or invalid settings.json / preprocessing_config.json"
        )

    suffix = os.path.splitext(file.filename or "")[1].lower()
    data = await file.read()
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(data)
        tmp_path = tmp.name

    try:
        if suffix == ".csv":
            raw = _read_csv(tmp_path)
        elif suffix == ".xes":
            if not xmlschema.is_valid(tmp_path, XSD_PATH):
                raise HTTPException(400, "XES file is not compliant with Xes.xsd")
            raw = pm4py.read_xes(tmp_path)
        else:
            raise HTTPException(400, "Unsupported file type; use .csv or .xes")

        if raw is None or raw.empty:
            raise HTTPException(400, "File is empty or could not be parsed")

        settings = config_loader.load_settings()
        pre_cfg = config_loader.load_preprocessing_config()

        df = preprocessor.apply_preprocessing(raw, pre_cfg)
        actor, event, logs, objects_, rating = (
            config_loader.settings_to_mapping_objects(settings)
        )
        timestamp_fields = config_loader.get_timestamp_fields(settings, event)

        graph_data = importer.build_graph_dataframes(
            df, actor, event, logs, objects_, rating,
            timestamp_fields, file.filename, int(time.time()),
        )
        summary = importer.bulk_load(get_connection(), graph_data)
        return {"status": "ok", "rows": int(len(df)), "summary": summary}
    finally:
        os.unlink(tmp_path)


@router.post("/inspect")
async def inspect_file(file: UploadFile = File(...)):
    """Read a file's columns (and a sample value each) without importing it.

    Drives the autocomplete in the interactive config editor.
    """
    suffix = os.path.splitext(file.filename or "")[1].lower()
    data = await file.read()
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(data)
        tmp_path = tmp.name
    try:
        if suffix == ".csv":
            raw = _read_csv(tmp_path)
        elif suffix == ".xes":
            if not xmlschema.is_valid(tmp_path, XSD_PATH):
                raise HTTPException(400, "XES file is not compliant with Xes.xsd")
            raw = pm4py.read_xes(tmp_path)
        else:
            raise HTTPException(400, "Unsupported file type; use .csv or .xes")

        columns = [str(c) for c in raw.columns]
        samples = {}
        for c in raw.columns:
            non_null = raw[c].dropna()
            samples[str(c)] = "" if non_null.empty else str(non_null.iloc[0])[:60]
        return {"columns": columns, "samples": samples, "rows": int(len(raw))}
    finally:
        os.unlink(tmp_path)
