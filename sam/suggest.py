from __future__ import annotations

import pandas as pd

from sam.time_utils import clean_token, duration_hours, format_hours, format_time, time_to_minutes

ANY_PLACE = "(Any place)"
GARAGE_TYPES = {"pull-out", "pull-in", "deadhead"}


def same_place(left: object, right: object) -> bool:
    return clean_token(left).casefold() == clean_token(right).casefold()


def trip_type(value: object) -> str:
    return clean_token(value).casefold()


def is_garage(value: object) -> bool:
    return trip_type(value) in GARAGE_TYPES


def _row(frame: pd.DataFrame, row_id: int) -> pd.Series:
    return frame.loc[frame["_id"] == row_id].iloc[0]


def ordered_ids(frame: pd.DataFrame, row_ids: list[int]) -> list[int]:
    if not row_ids:
        return []
    subset = frame.loc[frame["_id"].isin(row_ids), ["_id", "Start Time"]].copy()
    subset["_minutes"] = subset["Start Time"].map(time_to_minutes)
    subset = subset.sort_values(["_minutes", "_id"], na_position="last")
    return [int(value) for value in subset["_id"].tolist()]


def assignable_rows(frame: pd.DataFrame, include_garage: bool) -> pd.DataFrame:
    kind = frame["Type"].map(trip_type)
    keep_type = kind.eq("") | kind.eq("regular")
    if include_garage:
        keep_type = keep_type | kind.isin(GARAGE_TYPES)
    mask = (
        frame["Asn#"].map(clean_token).eq("")
        & keep_type
        & frame["Start Time"].map(time_to_minutes).notna()
        & frame["End Time"].map(time_to_minutes).notna()
    )
    return frame.loc[mask]


def first_open_block(
    frame: pd.DataFrame,
    blocks: list[str],
    include_garage: bool,
    hub: str,
    min_hours: float = 0,
    max_hours: float = 0,
) -> str:
    """First block that can hold a full shift. Falls back to the first block with any open trip."""
    if not blocks:
        return ""
    rows = assignable_rows(frame, include_garage)
    if rows.empty:
        return blocks[0]
    work = rows.copy()
    work["_block"] = work["Block"].map(clean_token)
    work["_start"] = work["Start Time"].map(time_to_minutes)
    grouped = {
        str(block): [int(value) for value in group.sort_values(["_start", "_id"])["_id"].tolist()]
        for block, group in work.groupby("_block", sort=False)
    }
    fallback = ""
    for block in blocks:
        ordered = grouped.get(block) or []
        start_id = find_start_id(frame, ordered, hub, None)
        if start_id is None:
            continue
        if not fallback:
            fallback = block
        if min_hours <= 0:
            return block
        chosen = cut_full_shift(frame, ordered, start_id, hub, min_hours, max_hours, None)
        hours = span_hours(frame, chosen)
        if hours is None or hours + 1e-9 < min_hours:
            continue
        if max_hours > 0 and hours - 1e-9 > max_hours:
            continue
        target = clean_token(_row(frame, chosen[0])["Start Location"]) if hub == ANY_PLACE else hub
        if same_place(_row(frame, chosen[-1])["End Location"], target):
            return block
    return fallback or blocks[0]


def open_counts(frame: pd.DataFrame, include_garage: bool) -> dict[str, int]:
    subset = assignable_rows(frame, include_garage)
    if subset.empty:
        return {}
    counts = subset["Block"].map(clean_token).value_counts()
    return {str(block): int(count) for block, count in counts.items()}


def eligible_ids(frame: pd.DataFrame, block: str, include_garage: bool) -> list[int]:
    subset = assignable_rows(frame, include_garage)
    subset = subset.loc[subset["Block"].map(clean_token).eq(clean_token(block))]
    return ordered_ids(frame, [int(value) for value in subset["_id"].tolist()])


def _gap_minutes(after_minutes: int, start_minutes: int) -> int:
    gap = start_minutes - after_minutes
    if gap < 0:
        gap += 24 * 60
    return gap


def find_start_id(
    frame: pd.DataFrame,
    ordered: list[int],
    hub: str,
    start_after: int | None,
) -> int | None:
    for row_id in ordered:
        row = _row(frame, row_id)
        start_minutes = time_to_minutes(row["Start Time"])
        if start_minutes is None:
            continue
        if start_after is not None and start_minutes < start_after:
            continue
        if hub != ANY_PLACE and not same_place(row["Start Location"], hub):
            continue
        return row_id
    return None


def find_connect_id(
    frame: pd.DataFrame,
    ordered: list[int],
    place: str,
    after_minutes: int,
    min_gap: int,
    max_gap: int,
) -> int | None:
    for row_id in ordered:
        row = _row(frame, row_id)
        if not same_place(row["Start Location"], place):
            continue
        start_minutes = time_to_minutes(row["Start Time"])
        if start_minutes is None:
            continue
        gap = _gap_minutes(after_minutes, start_minutes)
        if min_gap <= gap <= max_gap:
            return row_id
    return None


def connecting_blocks(
    frame: pd.DataFrame,
    place: str,
    after_minutes: int,
    include_garage: bool,
    min_gap: int,
    max_gap: int,
) -> list[dict[str, object]]:
    subset = assignable_rows(frame, include_garage)
    if subset.empty:
        return []
    work = subset.copy()
    work["_block"] = work["Block"].map(clean_token)
    work["_start"] = work["Start Time"].map(time_to_minutes)
    work = work.sort_values(["_start", "_id"])
    wanted = clean_token(place).casefold()
    found: list[dict[str, object]] = []
    seen: set[str] = set()
    for record in work.to_dict("records"):
        block = str(record["_block"])
        if not block or block in seen:
            continue
        if clean_token(record["Start Location"]).casefold() != wanted:
            continue
        start_minutes = record["_start"]
        if start_minutes is None or pd.isna(start_minutes):
            continue
        gap = _gap_minutes(after_minutes, int(start_minutes))
        if not (min_gap <= gap <= max_gap):
            continue
        seen.add(block)
        found.append(
            {
                "block": block,
                "row_id": int(record["_id"]),
                "route": clean_token(record["Route"]),
                "start": record["Start Time"],
                "gap": gap,
            }
        )
    found.sort(key=lambda item: time_to_minutes(item["start"]) or 0)
    return found


def _end_allowed(end_value: object, end_by: int | None) -> bool:
    if end_by is None:
        return True
    end_minutes = time_to_minutes(end_value)
    if end_minutes is None:
        return False
    return end_minutes <= end_by


def cut_full_shift(
    frame: pd.DataFrame,
    ordered: list[int],
    start_id: int,
    hub: str,
    min_hours: float,
    max_hours: float,
    end_by: int | None,
) -> list[int]:
    start_pos = ordered.index(start_id)
    running: list[int] = []
    candidates: list[list[int]] = []
    first_start = _row(frame, start_id)["Start Time"]
    target_place = clean_token(_row(frame, start_id)["Start Location"]) if hub == ANY_PLACE else hub

    for row_id in ordered[start_pos:]:
        row = _row(frame, row_id)
        if not _end_allowed(row["End Time"], end_by):
            break
        hours = duration_hours(first_start, row["End Time"])
        if running and hours is not None and max_hours > 0 and hours - 1e-9 > max_hours:
            break
        running.append(row_id)
        if hours is None:
            continue
        if hours + 1e-9 >= min_hours and same_place(row["End Location"], target_place):
            candidates.append(list(running))

    if candidates:
        target = (min_hours + max_hours) / 2 if max_hours > 0 else min_hours
        return min(
            candidates,
            key=lambda ids: abs((duration_hours(first_start, _row(frame, ids[-1])["End Time"]) or 0) - target),
        )
    return running


def cut_round_trip(
    frame: pd.DataFrame,
    ordered: list[int],
    start_id: int,
    hub: str,
    max_hours: float,
    end_by: int | None,
) -> list[int]:
    start_pos = ordered.index(start_id)
    running: list[int] = []
    first = _row(frame, start_id)
    target_place = clean_token(first["Start Location"]) if hub == ANY_PLACE else hub
    for row_id in ordered[start_pos:]:
        row = _row(frame, row_id)
        if not _end_allowed(row["End Time"], end_by):
            break
        hours = duration_hours(first["Start Time"], row["End Time"])
        if running and hours is not None and max_hours > 0 and hours - 1e-9 > max_hours:
            break
        running.append(row_id)
        if same_place(row["End Location"], target_place):
            break
    return running


def span_hours(frame: pd.DataFrame, row_ids: list[int]) -> float | None:
    if not row_ids:
        return None
    return duration_hours(_row(frame, row_ids[0])["Start Time"], _row(frame, row_ids[-1])["End Time"])


def interior_garage(frame: pd.DataFrame, block: str, row_ids: list[int]) -> list[str]:
    if len(row_ids) < 2:
        return []
    first_start = time_to_minutes(_row(frame, row_ids[0])["Start Time"])
    last_end = time_to_minutes(_row(frame, row_ids[-1])["End Time"])
    if first_start is None or last_end is None:
        return []
    notes: list[str] = []
    matched = frame.loc[frame["Block"].map(clean_token).eq(clean_token(block))]
    for _, row in matched.iterrows():
        if not is_garage(row["Type"]) or clean_token(row["Asn#"]):
            continue
        start_minutes = time_to_minutes(row["Start Time"])
        if start_minutes is None or start_minutes < first_start or start_minutes >= last_end:
            continue
        notes.append(f"{clean_token(row['Type'])} at {format_time(row['Start Time'])}")
    return notes


def describe_cut(
    frame: pd.DataFrame,
    row_ids: list[int],
    hub: str,
    min_hours: float,
    max_hours: float,
    mode: str,
    block: str,
) -> list[str]:
    warnings: list[str] = []
    if not row_ids:
        return ["No open trips matched this cut."]
    hours = span_hours(frame, row_ids)
    last = _row(frame, row_ids[-1])
    target = clean_token(_row(frame, row_ids[0])["Start Location"]) if hub == ANY_PLACE else hub
    if mode == "full" and hours is not None and min_hours > 0 and hours + 1e-9 < min_hours:
        warnings.append(f"This cut is {format_hours(hours)}, shorter than {min_hours:g} hours.")
    if hours is not None and max_hours > 0 and hours - 1e-9 > max_hours:
        warnings.append(f"This cut is {format_hours(hours)}, longer than {max_hours:g} hours.")
    if target and not same_place(last["End Location"], target):
        warnings.append(f"This cut does not end at {target}.")
    garage = interior_garage(frame, block, row_ids)
    if garage:
        shown = ", ".join(garage[:3])
        extra = f" and {len(garage) - 3} more" if len(garage) > 3 else ""
        warnings.append(f"Left blank inside this shift: {shown}{extra}.")
    return warnings


def last_assigned_row(frame: pd.DataFrame, label: str) -> pd.Series | None:
    matched = frame.loc[frame["Asn#"].map(clean_token).eq(clean_token(label))].copy()
    if matched.empty:
        return None
    matched["_end"] = matched["End Time"].map(time_to_minutes)
    matched = matched.sort_values(["_end", "_id"], na_position="last")
    return matched.iloc[-1]


def propose_label(frame: pd.DataFrame, requested: str) -> str:
    text = clean_token(requested)
    if text:
        return text
    return str(_next_number(frame))


def _next_number(frame: pd.DataFrame) -> int:
    highest = 0
    for value in frame["Asn#"].tolist():
        text = clean_token(value)
        if text.isdigit():
            highest = max(highest, int(text))
    return highest + 1


def label_exists(frame: pd.DataFrame, label: str) -> bool:
    text = clean_token(label)
    if not text:
        return False
    return bool(frame["Asn#"].map(clean_token).eq(text).any())
