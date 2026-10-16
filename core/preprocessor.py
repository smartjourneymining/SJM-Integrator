"""
Non-UI preprocessing: map raw CSV/XES columns to standard field names and apply
static values / auto-generation. Extracted from PreprocessorUI.finish_preprocessing
so it can run headlessly from the import API.

config keys (from preprocessing_config.json):
  mappings:      {standard_field: csv_column}
  static_values: {standard_field: value}        # fallback if mapped & NULL, else set all
  auto_generate: {standard_field: gen_type}      # same fallback semantics
  skip_fields:   [standard_field, ...]
"""
import uuid

import pandas as pd


def apply_preprocessing(raw_df, config):
    mappings = config.get("mappings", {})
    static_values = config.get("static_values", {})
    auto_generate = config.get("auto_generate", {})
    skip_fields = set(config.get("skip_fields", []))

    df = raw_df.copy()
    original_columns = list(raw_df.columns)

    # Group mappings by CSV column to handle one-to-many (excluding skipped).
    csv_to_standards = {}
    for std, csv_col in mappings.items():
        if std in skip_fields:
            continue
        csv_to_standards.setdefault(csv_col, []).append(std)

    rename_map = {}
    copy_map = {}
    for csv_col, stds in csv_to_standards.items():
        stds = [s for s in stds if s not in skip_fields]
        if not stds or csv_col not in df.columns:
            continue
        if len(stds) == 1:
            rename_map[csv_col] = stds[0]
        else:
            copy_map[csv_col] = stds

    # One-to-many copies first (before renames), then drop the source columns.
    drop_after_copy = []
    for csv_col, stds in copy_map.items():
        for std in stds:
            if std not in skip_fields:
                df[std] = df[csv_col].copy()
        drop_after_copy.append(csv_col)
    if drop_after_copy:
        df.drop(columns=drop_after_copy, inplace=True)

    df.rename(columns=rename_map, inplace=True)

    # Static values: fallback for NULLs when mapped, else set on all rows.
    for std, value in static_values.items():
        if std in skip_fields:
            continue
        if std in mappings and std in df.columns:
            null_mask = df[std].isna() | (df[std] == "")
            df.loc[null_mask, std] = value
        elif std not in mappings:
            df[std] = value

    # Auto-generation: fallback for NULLs when mapped, else generate for all rows.
    for std, gen_type in auto_generate.items():
        if std in skip_fields:
            continue
        mapped = std in mappings and std in df.columns
        if mapped:
            null_mask = df[std].isna() | (df[std] == "")
            n = int(null_mask.sum())
            if n == 0:
                continue
            df.loc[null_mask, std] = _generate(gen_type, n, df, std, null_mask)
        else:
            df[std] = _generate(gen_type, len(df), df, std, None)

    # Drop skipped fields and any leftover original CSV columns.
    for fld in skip_fields:
        if fld in df.columns:
            df.drop(columns=[fld], inplace=True)
    leftover = [c for c in df.columns if c in original_columns and c not in mappings.values()]
    if leftover:
        df.drop(columns=leftover, inplace=True)

    return df


def _generate(gen_type, n, df, std, null_mask):
    """Produce n generated values for the given generation type."""
    if gen_type == "Auto-increment (numeric)":
        start = 1
        if null_mask is not None:
            try:
                start = int(df[std].dropna().astype(int).max()) + 1
            except (ValueError, TypeError):
                start = 1
        return list(range(start, start + n))
    if gen_type == "Auto-increment (ID1, ID2, ...)":
        start = 1
        if null_mask is not None:
            try:
                existing = df[std].dropna().astype(str)
                start = max(int(x[2:]) for x in existing if x.startswith("ID")) + 1
            except (ValueError, TypeError):
                start = 1
        return [f"ID{i}" for i in range(start, start + n)]
    if gen_type == "UUID":
        return [str(uuid.uuid4()) for _ in range(n)]
    if gen_type == "Row number":
        if null_mask is not None:
            return (df[null_mask].index + 1).tolist()
        return list(range(1, n + 1))
    # Unknown generation type: leave blanks.
    return [""] * n
