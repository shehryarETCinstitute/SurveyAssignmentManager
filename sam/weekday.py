from __future__ import annotations

from io import BytesIO

import pandas as pd

from sam.time_utils import clean_token, time_to_minutes

RAW_REQUIRED = {
    "block",
    "route",
    "start",
    "end",
    "trip start place description",
    "trip end place description",
    "type",
}
WEEKDAY_REQUIRED = {
    "asn#",
    "block",
    "route",
    "direction",
    "start time",
    "start location",
    "end location",
    "end time",
}
KEEP_COLUMNS = [
    "Asn#",
    "Block",
    "Route",
    "Direction",
    "Start Time",
    "Start Location",
    "End Location",
    "End Time",
    "Type",
    "Garage",
    "Veh1",
    "Duty",
]


def _names(columns) -> set[str]:
    return {str(column).strip().lower() for column in columns}


def classify_columns(columns) -> str | None:
    names = _names(columns)
    if RAW_REQUIRED <= names:
        return "raw"
    if WEEKDAY_REQUIRED <= names:
        return "weekday"
    return None


def _lookup(columns) -> dict[str, str]:
    return {str(column).strip().lower(): column for column in columns}


def _series(frame: pd.DataFrame, *aliases: str) -> pd.Series:
    lookup = _lookup(frame.columns)
    for alias in aliases:
        source = lookup.get(alias)
        if source is not None:
            return frame[source].map(clean_token)
    return pd.Series([""] * len(frame), index=frame.index)


def _clock(frame: pd.DataFrame, *aliases: str) -> pd.Series:
    lookup = _lookup(frame.columns)
    for alias in aliases:
        source = lookup.get(alias)
        if source is not None:
            return pd.to_datetime(frame[source], errors="coerce")
    return pd.Series(pd.NaT, index=frame.index)


def _with_ids(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.loc[:, KEEP_COLUMNS].copy()
    frame.insert(0, "_id", range(len(frame)))
    frame["Asn#"] = frame["Asn#"].map(clean_token)
    return frame.reset_index(drop=True)


def frame_from_raw(frame: pd.DataFrame) -> pd.DataFrame:
    built = pd.DataFrame(
        {
            "Asn#": "",
            "Block": _series(frame, "block"),
            "Route": _series(frame, "route"),
            "Direction": _series(frame, "direction"),
            "Start Time": _clock(frame, "start"),
            "Start Location": _series(frame, "trip start place description"),
            "End Location": _series(frame, "trip end place description"),
            "End Time": _clock(frame, "end"),
            "Type": _series(frame, "type"),
            "Garage": _series(frame, "garage"),
            "Veh1": _series(frame, "veh1"),
            "Duty": _series(frame, "duty"),
        }
    )
    built = built.loc[built["Block"].ne("")].copy()
    return _with_ids(built)


def frame_from_weekday(frame: pd.DataFrame) -> pd.DataFrame:
    built = pd.DataFrame(
        {
            "Asn#": _series(frame, "asn#"),
            "Block": _series(frame, "block"),
            "Route": _series(frame, "route"),
            "Direction": _series(frame, "direction"),
            "Start Time": _clock(frame, "start time"),
            "Start Location": _series(frame, "start location"),
            "End Location": _series(frame, "end location"),
            "End Time": _clock(frame, "end time"),
            "Type": _series(frame, "type"),
            "Garage": _series(frame, "garage"),
            "Veh1": _series(frame, "veh1"),
            "Duty": _series(frame, "duty"),
        }
    )
    built = built.loc[built["Block"].ne("")].copy()
    return _with_ids(built)


def inspect_workbook(data: bytes) -> list[dict[str, object]]:
    book = pd.ExcelFile(BytesIO(data))
    options: list[dict[str, object]] = []
    for name in book.sheet_names:
        header = pd.read_excel(book, sheet_name=name, nrows=0)
        kind = classify_columns(header.columns)
        if kind is None:
            continue
        counted = pd.read_excel(book, sheet_name=name, usecols=[0])
        assigned = 0
        if kind == "weekday":
            lookup = _lookup(header.columns)
            asn_col = lookup.get("asn#")
            if asn_col is not None:
                asn = pd.read_excel(book, sheet_name=name, usecols=[asn_col])
                assigned = int(asn.iloc[:, 0].map(clean_token).ne("").sum())
        options.append(
            {
                "name": name,
                "kind": kind,
                "rows": int(len(counted)),
                "assigned": assigned,
            }
        )
    return options


def load_sheet(data: bytes, sheet_name: str, kind: str) -> pd.DataFrame:
    frame = pd.read_excel(BytesIO(data), sheet_name=sheet_name, dtype=object)
    frame.columns = [str(column).strip() for column in frame.columns]
    if kind == "raw":
        return frame_from_raw(frame)
    if kind == "weekday":
        return frame_from_weekday(frame)
    raise ValueError(f"Sheet {sheet_name} is not a Raw Weekday or Weekday sheet.")


def auto_choice(options: list[dict[str, object]]) -> dict[str, object] | None:
    """Prefer a sheet that is clearly the raw weekday extract."""
    named_raw = [
        item
        for item in options
        if item["kind"] == "raw" and _is_raw_weekday_name(str(item["name"]))
    ]
    if len(named_raw) == 1:
        return named_raw[0]
    if len(options) == 1:
        return options[0]
    raw_sheets = [item for item in options if item["kind"] == "raw"]
    weekday_sheets = [item for item in options if item["kind"] == "weekday"]
    assigned = sum(int(item["assigned"]) for item in weekday_sheets)
    if len(raw_sheets) == 1 and assigned == 0:
        return raw_sheets[0]
    return None


def _is_raw_weekday_name(name: str) -> bool:
    text = name.casefold()
    return "raw" in text and "weekday" in text


def has_type_column(frame: pd.DataFrame) -> bool:
    return bool(frame["Type"].map(clean_token).ne("").any())


def next_assignment_number(frame: pd.DataFrame) -> int:
    highest = 0
    for value in frame["Asn#"].tolist():
        text = clean_token(value)
        if text.isdigit():
            highest = max(highest, int(text))
    return highest + 1


def default_hub(frame: pd.DataFrame, preferred: str) -> str:
    if preferred:
        for value in frame["Start Location"].map(clean_token):
            if value.casefold() == preferred.casefold():
                return value
    regular = frame.loc[frame["Type"].map(lambda value: clean_token(value).casefold()).eq("regular"), "Start Location"]
    pool = regular if not regular.empty else frame["Start Location"]
    counts = pool.map(clean_token)
    counts = counts[counts.ne("")]
    if counts.empty:
        return ""
    return str(counts.value_counts().index[0])


def block_sort_key(value: str) -> tuple:
    text = clean_token(value)
    if text.isdigit():
        return (0, int(text))
    return (1, text.casefold())


def open_regular_count(frame: pd.DataFrame) -> int:
    blank = frame["Asn#"].map(clean_token).eq("")
    kind = frame["Type"].map(lambda value: clean_token(value).casefold())
    regular_or_blank = kind.eq("regular") | kind.eq("")
    timed = frame["Start Time"].map(time_to_minutes).notna()
    return int((blank & regular_or_blank & timed).sum())
