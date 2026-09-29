from __future__ import annotations

import html

import pandas as pd
import streamlit as st

from sam.config import (
    APP_NAME,
    DEFAULT_HUB,
    DEFAULT_MAX_HOURS,
    DEFAULT_MIN_HOURS,
    MAX_SWITCH_MINUTES,
    MIN_SWITCH_MINUTES,
)
from sam.exporting import assignment_labels, packet_bytes, packets_zip, workbook_bytes
from sam.suggest import (
    ANY_PLACE,
    connecting_blocks,
    cut_full_shift,
    cut_round_trip,
    describe_cut,
    eligible_ids,
    find_connect_id,
    find_start_id,
    first_open_block,
    is_garage,
    open_counts,
    label_exists,
    last_assigned_row,
    propose_label,
    same_place,
    span_hours,
)
from sam.time_utils import (
    clean_token,
    clock_input_to_minutes,
    duration_hours,
    format_hours,
    format_time,
    subtract_minutes,
    time_to_minutes,
)
from sam.weekday import (
    auto_choice,
    block_sort_key,
    default_hub,
    has_type_column,
    inspect_workbook,
    load_sheet,
    next_assignment_number,
    open_regular_count,
)

SUGGESTED = "Suggested"
ASSIGNED = "Assigned"
GARAGE = "Garage"
OPEN = "Open"


def _seed(key: str, value) -> None:
    if key not in st.session_state:
        st.session_state[key] = value


def _selected_rows(state) -> list[int]:
    if state is None:
        return []
    selection = state.get("selection") if isinstance(state, dict) else getattr(state, "selection", None)
    if selection is None:
        return []
    rows = selection.get("rows") if isinstance(selection, dict) else getattr(selection, "rows", None)
    return list(rows or [])


def _clear_work() -> None:
    for key in (
        "frame",
        "notes",
        "suggestion",
        "undo",
        "revision",
        "excel_bytes",
        "excel_rev",
        "word_zip",
        "word_rev",
        "upload_bytes",
        "upload_name",
        "upload_token",
        "sheet_options",
        "builder_name",
        "builder_block",
        "builder_hub",
        "include_garage",
        "choose_any_block",
        "cut_note",
        "min_hours",
        "max_hours",
        "use_start_after",
        "start_after_time",
        "use_end_by",
        "end_by_time",
        "min_switch",
        "max_switch",
        "made_table",
        "flash",
        "_pick_token",
        "_clear_note",
        "packet_cache",
    ):
        st.session_state.pop(key, None)
    st.session_state["uploader_key"] = int(st.session_state.get("uploader_key", 0)) + 1


def _load_choice(option: dict[str, object]) -> None:
    frame = load_sheet(st.session_state["upload_bytes"], str(option["name"]), str(option["kind"]))
    st.session_state["frame"] = frame
    st.session_state["notes"] = {}
    st.session_state["suggestion"] = None
    st.session_state["undo"] = None
    st.session_state["revision"] = 0
    st.session_state["excel_bytes"] = None
    st.session_state["word_zip"] = None
    st.session_state["source_sheet"] = option["name"]
    st.session_state["source_kind"] = option["kind"]
    st.session_state["packet_cache"] = {}
    for key in (
        "builder_name",
        "builder_block",
        "builder_hub",
        "suggestion",
        "made_table",
        "_pick_token",
    ):
        st.session_state.pop(key, None)


def _inject_css() -> None:
    st.markdown(
        """
        <style>
        .stApp:has(.sam-mark) header[data-testid="stHeader"] {
            background: transparent;
        }
        .stApp:has(.sam-mark) .block-container {
            padding-top: 1.4rem;
            max-width: 1280px;
        }
        .stApp:has(.sam-mark) [data-testid="stFileUploader"] {
            background: #ffffff;
            border: 1px dashed #cfc6b8;
            border-radius: 16px;
            padding: 0.4rem 0.6rem 0.2rem;
        }
        .sam-kicker {
            margin: 0;
            color: #0F6E56;
            font-size: 0.78rem;
            font-weight: 700;
            letter-spacing: 0.08em;
            text-transform: uppercase;
        }
        .sam-title {
            margin: 0.15rem 0 0.2rem;
            font-size: 2rem;
            line-height: 1.1;
            color: #1C1917;
        }
        .sam-sub {
            margin: 0;
            color: #57534E;
            font-size: 1.02rem;
        }
        .sam-banner {
            background: #ffffff;
            border: 1px solid #e7e2d8;
            border-left: 6px solid #0F6E56;
            border-radius: 16px;
            padding: 1rem 1.15rem 0.9rem;
            margin: 0.4rem 0 0.8rem;
        }
        .sam-banner h2 {
            margin: 0.15rem 0;
            font-size: 1.7rem;
            color: #1C1917;
        }
        .sam-banner p { margin: 0.15rem 0; color: #44403C; }
        .sam-warn {
            background: #FFF7ED;
            color: #9A3412;
            border-radius: 10px;
            padding: 0.45rem 0.7rem;
            margin-top: 0.45rem;
        }
        .sam-steps {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 0.8rem;
            margin: 1rem 0 1.2rem;
        }
        .sam-step {
            background: #ffffff;
            border: 1px solid #e7e2d8;
            border-radius: 16px;
            padding: 0.9rem 1rem;
        }
        .sam-step strong { display: block; margin-bottom: 0.25rem; }
        .sam-step span { color: #57534E; }
        .sam-mark { display: none; }
        @media (max-width: 800px) {
            .sam-steps { grid-template-columns: 1fr; }
        }
        </style>
        <div class="sam-mark"></div>
        """,
        unsafe_allow_html=True,
    )


def _header(subtitle: str) -> None:
    st.markdown(
        f"""
        <p class="sam-kicker">Field work</p>
        <h1 class="sam-title">{html.escape(APP_NAME)}</h1>
        <p class="sam-sub">{html.escape(subtitle)}</p>
        """,
        unsafe_allow_html=True,
    )


def _summary(frame: pd.DataFrame, notes: dict) -> pd.DataFrame:
    records = []
    for label in assignment_labels(frame):
        matched = frame.loc[frame["Asn#"].map(clean_token).eq(label)]
        ids = [int(value) for value in matched["_id"].tolist()]
        ids = sorted(ids, key=lambda row_id: time_to_minutes(frame.loc[frame["_id"].eq(row_id), "Start Time"].iloc[0]) or 0)
        first = frame.loc[frame["_id"].eq(ids[0])].iloc[0]
        last = frame.loc[frame["_id"].eq(ids[-1])].iloc[0]
        blocks = list(dict.fromkeys(clean_token(frame.loc[frame["_id"].eq(row_id), "Block"].iloc[0]) for row_id in ids))
        records.append(
            {
                "Assignment": label,
                "Trips": len(ids),
                "Blocks": ", ".join(blocks),
                "From": format_time(first["Start Time"]),
                "To": format_time(last["End Time"]),
                "Hours": format_hours(duration_hours(first["Start Time"], last["End Time"])),
                "Notes": len(notes.get(label, [])),
            }
        )
    return pd.DataFrame(records)


def _block_table(frame: pd.DataFrame, block: str, suggested: set[int]) -> pd.DataFrame:
    matched = frame.loc[frame["Block"].map(clean_token).eq(clean_token(block))].copy()
    matched["_sort"] = matched["Start Time"].map(lambda value: time_to_minutes(value) if time_to_minutes(value) is not None else 99999)
    matched = matched.sort_values(["_sort", "_id"])
    rows = []
    for _, row in matched.iterrows():
        row_id = int(row["_id"])
        if row_id in suggested:
            status = SUGGESTED
        elif clean_token(row["Asn#"]):
            status = ASSIGNED
        elif is_garage(row["Type"]):
            status = GARAGE
        elif time_to_minutes(row["Start Time"]) is None:
            status = "No time"
        else:
            status = OPEN
        rows.append(
            {
                "Start": format_time(row["Start Time"]),
                "End": format_time(row["End Time"]),
                "Route": clean_token(row["Route"]),
                "Dir": clean_token(row["Direction"]),
                "From": clean_token(row["Start Location"]),
                "To": clean_token(row["End Location"]),
                "Type": clean_token(row["Type"]),
                "Assignment": clean_token(row["Asn#"]),
                "Status": status,
            }
        )
    return pd.DataFrame(rows)


def _paint(table: pd.DataFrame):
    def paint_row(row: pd.Series) -> list[str]:
        status = row["Status"]
        if status == SUGGESTED:
            style = "background-color: #D1FAE5; color: #064E3B"
        elif status == ASSIGNED:
            style = "background-color: #EEF2FF; color: #312E81"
        elif status == GARAGE:
            style = "background-color: #F3F4F6; color: #6B7280"
        else:
            style = ""
        return [style] * len(row)

    if table.empty:
        return table
    return table.style.apply(paint_row, axis=1)


def _route_path(frame: pd.DataFrame, row_ids: list[int]) -> str:
    routes: list[str] = []
    for row_id in row_ids:
        route = clean_token(frame.loc[frame["_id"].eq(row_id), "Route"].iloc[0])
        if route and (not routes or routes[-1] != route):
            routes.append(route)
    return ", ".join(routes)


def _make_cut(
    frame: pd.DataFrame,
    *,
    block: str,
    hub: str,
    start_after: int | None,
    end_by: int | None,
    min_hours: float,
    max_hours: float,
    include_garage: bool,
    mode: str,
    connect: tuple[str, int] | None,
) -> tuple[dict | None, str | None]:
    ordered = eligible_ids(frame, block, include_garage)
    if not ordered:
        return None, "This block has no open trips left."
    if connect is not None:
        place, after_minutes = connect
        start_id = find_connect_id(
            frame,
            ordered,
            place,
            after_minutes,
            int(st.session_state.get("min_switch", MIN_SWITCH_MINUTES)),
            int(st.session_state.get("max_switch", MAX_SWITCH_MINUTES)),
        )
        if start_id is None:
            start_id = find_start_id(frame, ordered, place, after_minutes)
        if start_id is None:
            return None, f"No open trip on block {block} leaves {place} after {format_time(_minutes_to_dummy(after_minutes))}."
    else:
        start_id = find_start_id(frame, ordered, hub, start_after)
        if start_id is None:
            where = "the first open trip" if hub == ANY_PLACE else hub
            return None, f"No open trip on block {block} starts at {where}."
    if mode == "round":
        row_ids = cut_round_trip(frame, ordered, start_id, hub if connect is None else connect[0], max_hours, end_by)
    else:
        row_ids = cut_full_shift(frame, ordered, start_id, hub, min_hours, max_hours, end_by)
    if not row_ids:
        return None, "Nothing in this block fits the end time."
    return {
        "row_ids": row_ids,
        "eligible_ids": ordered,
        "block": clean_token(block),
        "mode": mode,
        "include_garage": include_garage,
        "hub": hub if connect is None else connect[0],
    }, None


def _minutes_to_dummy(minutes: int):
    hour, minute = divmod(int(minutes) % (24 * 60), 60)
    return pd.Timestamp(2000, 1, 1, hour, minute)


def _suggestion_is_current(suggestion: dict | None, block: str, include_garage: bool) -> bool:
    if not suggestion:
        return False
    return clean_token(suggestion.get("block")) == clean_token(block) and bool(suggestion.get("include_garage")) == bool(include_garage)


def _accept(frame: pd.DataFrame, suggestion: dict, label: str, note: str) -> None:
    row_ids = [int(value) for value in suggestion["row_ids"]]
    current = frame.loc[frame["_id"].isin(row_ids), ["_id", "Asn#"]]
    if current["Asn#"].map(clean_token).ne("").any():
        raise ValueError("One of these trips was already assigned. Suggest the shift again.")
    previous = {int(row["_id"]): clean_token(row["Asn#"]) for _, row in current.iterrows()}
    frame.loc[frame["_id"].isin(row_ids), "Asn#"] = label
    st.session_state["frame"] = frame
    added_note = False
    text = note.strip()
    if text:
        st.session_state["notes"].setdefault(label, []).append({"after_row_id": row_ids[-1], "text": text})
        added_note = True
    st.session_state["undo"] = {"ids": row_ids, "old": previous, "label": label, "note": added_note}
    st.session_state["suggestion"] = None
    st.session_state["revision"] = int(st.session_state.get("revision", 0)) + 1
    st.session_state["packet_cache"] = {}
    hours = span_hours(frame, row_ids)
    st.session_state["flash"] = (
        f"Saved {label}: {len(row_ids)} trips, {format_hours(hours)}."
    )
    st.session_state["_clear_note"] = True


def _undo(frame: pd.DataFrame) -> None:
    undo = st.session_state.get("undo")
    if not undo:
        return
    for row_id, previous in undo["old"].items():
        frame.loc[frame["_id"].eq(int(row_id)), "Asn#"] = previous
    if undo.get("note"):
        notes = st.session_state["notes"].get(undo["label"], [])
        if notes:
            notes.pop()
    st.session_state["frame"] = frame
    st.session_state["undo"] = None
    st.session_state["revision"] = int(st.session_state.get("revision", 0)) + 1
    st.session_state["packet_cache"] = {}
    st.session_state["flash"] = f"Undid {undo['label']}."


def _unassign(frame: pd.DataFrame, label: str) -> None:
    label = clean_token(label)
    if not label:
        return
    mask = frame["Asn#"].map(clean_token).eq(label)
    count = int(mask.sum())
    if count == 0:
        return
    frame.loc[mask, "Asn#"] = ""
    st.session_state["frame"] = frame
    notes = st.session_state.setdefault("notes", {})
    notes.pop(label, None)
    undo = st.session_state.get("undo") or {}
    if clean_token(undo.get("label")) == label:
        st.session_state["undo"] = None
    st.session_state["suggestion"] = None
    st.session_state["revision"] = int(st.session_state.get("revision", 0)) + 1
    st.session_state["packet_cache"] = {}
    st.session_state["_clear_selection"] = True
    st.session_state["_clear_builder_name"] = True
    st.session_state["flash"] = f"Unassigned {label}. {count} trips are open again."


def _upload_screen() -> None:
    _header("Upload the Raw Weekday file. The working sheet is built from it, and every shift is previewed before it is saved.")
    st.markdown(
        """
        <div class="sam-steps">
            <div class="sam-step"><strong>1. Load Raw Weekday</strong><span>Garage moves stay visible and are left blank.</span></div>
            <div class="sam-step"><strong>2. Preview the cut</strong><span>A full shift, or a short piece for someone who changes buses.</span></div>
            <div class="sam-step"><strong>3. Save once</strong><span>The same label lands on the Weekday rows. Download the packet.</span></div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    uploaded = st.file_uploader(
        "Weekday workbook",
        type=["xlsx", "xlsm"],
        key=f"uploader_{st.session_state.get('uploader_key', 0)}",
        label_visibility="collapsed",
    )
    if uploaded is not None:
        token = (uploaded.name, uploaded.size)
        if token != st.session_state.get("upload_token"):
            data = uploaded.getvalue()
            try:
                options = inspect_workbook(data)
            except Exception as exc:
                st.error(f"Could not read that workbook. {exc}")
                return
            st.session_state["upload_bytes"] = data
            st.session_state["upload_name"] = uploaded.name
            st.session_state["upload_token"] = token
            st.session_state["sheet_options"] = options
            if not options:
                st.error("No Raw Weekday or Weekday sheet was found. The raw sheet needs Block, Route, Start, End, trip place names, and Type.")
                return
            choice = auto_choice(options)
            if choice is not None:
                try:
                    _load_choice(choice)
                except Exception as exc:
                    st.error(str(exc))
                    return
                st.rerun()

    options = st.session_state.get("sheet_options") or []
    if options and st.session_state.get("frame") is None:
        st.subheader("Which sheet should be the working copy?")
        st.caption("Raw Weekday starts blank. A Weekday sheet keeps assignment names that are already filled in.")
        for option in options:
            if option["kind"] == "raw":
                detail = f"{option['name']} · {int(option['rows']):,} rows · start with blank assignments"
            else:
                detail = f"{option['name']} · {int(option['rows']):,} rows · {int(option['assigned']):,} already assigned"
            if st.button(detail, key=f"pick_{option['name']}", use_container_width=True):
                try:
                    _load_choice(option)
                except Exception as exc:
                    st.error(str(exc))
                    return
                st.rerun()


def _workspace() -> None:
    frame: pd.DataFrame = st.session_state["frame"]
    notes: dict = st.session_state.setdefault("notes", {})
    if st.session_state.pop("_clear_note", False):
        st.session_state["cut_note"] = ""
    if st.session_state.pop("_clear_selection", False):
        st.session_state.pop("made_table", None)
    if st.session_state.pop("_clear_builder_name", False):
        st.session_state["builder_name"] = ""
        st.session_state.pop("_pick_token", None)
    flash = st.session_state.pop("flash", None)

    summary = _summary(frame, notes)
    picked = _selected_rows(st.session_state.get("made_table"))
    if picked and not summary.empty and picked[0] < len(summary):
        label = str(summary.iloc[picked[0]]["Assignment"])
        token = f"{label}:{picked[0]}"
        if token != st.session_state.get("_pick_token"):
            st.session_state["builder_name"] = label
            st.session_state["_pick_token"] = token
    _seed("builder_name", "")

    kind = "Raw Weekday" if st.session_state.get("source_kind") == "raw" else "Weekday"
    _header(f"{st.session_state.get('upload_name', 'Workbook')} · {kind} sheet “{st.session_state.get('source_sheet', '')}”")
    if flash:
        st.success(flash)

    open_count = open_regular_count(frame)
    assigned_labels = assignment_labels(frame)
    metric_cols = st.columns([1, 1, 1, 1, 1.3])
    metric_cols[0].metric("Trips", f"{len(frame):,}")
    metric_cols[1].metric("Open regular", f"{open_count:,}")
    metric_cols[2].metric("Assignments", f"{len(assigned_labels):,}")
    metric_cols[3].metric("Next number", str(next_assignment_number(frame)))
    with metric_cols[4]:
        st.write("")
        if st.button("New file", use_container_width=True):
            _clear_work()
            st.rerun()

    other_sheets = [
        option
        for option in (st.session_state.get("sheet_options") or [])
        if option.get("name") != st.session_state.get("source_sheet")
    ]
    if other_sheets:
        with st.expander("Other sheets in this workbook"):
            st.caption("Raw Weekday is the fresh start. Open Weekday only when you want to keep numbers already saved there.")
            for option in other_sheets:
                if option["kind"] == "raw":
                    detail = f"Use {option['name']} · blank assignments"
                else:
                    detail = f"Use {option['name']} · {int(option['assigned']):,} already assigned"
                if st.button(detail, key=f"switch_{option['name']}"):
                    _load_choice(option)
                    st.rerun()

    include_ready = has_type_column(frame)
    locations = frame["Start Location"].map(clean_token)
    location_choices = [ANY_PLACE] + [value for value in locations.value_counts().index.tolist() if value]
    _seed("builder_hub", default_hub(frame, DEFAULT_HUB) or (location_choices[1] if len(location_choices) > 1 else ANY_PLACE))
    _seed("include_garage", False)
    _seed("min_hours", float(DEFAULT_MIN_HOURS))
    _seed("max_hours", float(DEFAULT_MAX_HOURS))
    _seed("min_switch", int(MIN_SWITCH_MINUTES))
    _seed("max_switch", int(MAX_SWITCH_MINUTES))
    _seed("use_start_after", False)
    _seed("use_end_by", False)
    _seed("choose_any_block", False)

    name_now = clean_token(st.session_state.get("builder_name"))
    continuing = label_exists(frame, name_now)
    last = last_assigned_row(frame, name_now) if continuing else None
    include_garage = bool(st.session_state.get("include_garage"))

    left, right = st.columns([0.92, 1.08], gap="large")
    with left:
        with st.container(border=True):
            st.markdown("**Cut a shift**")
            st.text_input(
                "Assignment name",
                key="builder_name",
                placeholder="Blank uses the next number",
                help="Type a name such as Aisha 1 to keep adding pieces to the same person. Leave it blank for 1, 2, 3.",
            )
            name_now = clean_token(st.session_state.get("builder_name"))
            continuing = label_exists(frame, name_now)
            last = last_assigned_row(frame, name_now) if continuing else None
            if include_ready:
                st.checkbox(
                    "Include garage moves",
                    key="include_garage",
                    help="Pull-out, pull-in, and deadhead. Leave this off for a normal shift. Turn it on for express.",
                )
            include_garage = bool(st.session_state.get("include_garage")) if include_ready else True
            connect_options: list[dict[str, object]] = []
            if continuing and last is not None:
                end_minutes = time_to_minutes(last["End Time"]) or 0
                st.caption(
                    f"{name_now} is at {clean_token(last['End Location'])} at {format_time(last['End Time'])}."
                )
                st.checkbox("Choose any block", key="choose_any_block")
                if not st.session_state.get("choose_any_block"):
                    connect_options = connecting_blocks(
                        frame,
                        clean_token(last["End Location"]),
                        end_minutes,
                        include_garage,
                        int(st.session_state["min_switch"]),
                        int(st.session_state["max_switch"]),
                    )
            else:
                st.selectbox("Start at", location_choices, key="builder_hub")

            blocks = sorted(
                {clean_token(value) for value in frame["Block"].tolist() if clean_token(value)},
                key=block_sort_key,
            )
            connect_map = {str(item["block"]): item for item in connect_options}
            if continuing and last is not None and not st.session_state.get("choose_any_block"):
                block_options = [str(item["block"]) for item in connect_options]
            else:
                block_options = blocks
            if block_options and st.session_state.get("builder_block") not in block_options:
                if st.session_state.get("builder_block") is None and not continuing:
                    st.session_state["builder_block"] = first_open_block(
                        frame,
                        block_options,
                        include_garage,
                        str(st.session_state.get("builder_hub") or ANY_PLACE),
                        float(st.session_state.get("min_hours") or 0),
                        float(st.session_state.get("max_hours") or 0),
                    )
                else:
                    st.session_state["builder_block"] = block_options[0]

            open_by_block = open_counts(frame, include_garage)

            def block_label(block: str) -> str:
                item = connect_map.get(block)
                if item is not None:
                    return (
                        f"{block}   ·   {format_time(item['start'])}   ·   route {item['route']}"
                        f"   ·   {int(item['gap'])} min"
                    )
                return f"{block}   ·   {open_by_block.get(block, 0)} open"

            if not block_options:
                st.info("No open trip leaves that place inside the switch window. Widen it under More options, or choose any block.")
                selected_block = ""
            else:
                selected_block = st.selectbox("Block", block_options, key="builder_block", format_func=block_label)

            with st.expander("More options"):
                hour_left, hour_right = st.columns(2)
                min_hours = hour_left.number_input("No shorter than (hours)", min_value=0.0, max_value=24.0, step=0.5, key="min_hours")
                max_hours = hour_right.number_input("No longer than (hours)", min_value=0.0, max_value=24.0, step=0.5, key="max_hours")
                if not continuing:
                    st.checkbox("Start after a clock time", key="use_start_after")
                    if st.session_state.get("use_start_after"):
                        _seed("start_after_time", pd.Timestamp("05:00").time())
                        st.time_input("Start after", key="start_after_time", step=300)
                st.checkbox("End by a clock time", key="use_end_by")
                if st.session_state.get("use_end_by"):
                    _seed("end_by_time", pd.Timestamp("14:30").time())
                    st.time_input("End by", key="end_by_time", step=300)
                gap_left, gap_right = st.columns(2)
                gap_left.number_input("Minutes to change buses, at least", min_value=0, max_value=240, step=5, key="min_switch")
                gap_right.number_input("Minutes to change buses, at most", min_value=0, max_value=240, step=5, key="max_switch")

            min_hours = float(st.session_state["min_hours"])
            max_hours = float(st.session_state["max_hours"])
            if min_hours > 0 and max_hours > 0 and min_hours > max_hours:
                st.warning("The shortest length is greater than the longest length.")
            start_after = clock_input_to_minutes(st.session_state.get("start_after_time")) if st.session_state.get("use_start_after") and not continuing else None
            end_by = clock_input_to_minutes(st.session_state.get("end_by_time")) if st.session_state.get("use_end_by") else None
            hub = st.session_state.get("builder_hub") or ANY_PLACE

            if continuing and last is not None:
                rule = (
                    f"Next piece of {name_now}: a round trip that leaves "
                    f"{clean_token(last['End Location'])} after {format_time(last['End Time'])}."
                )
            else:
                where = "any place" if hub == ANY_PLACE else str(hub)
                rule = (
                    f"Full shift on block {selected_block or '—'}: open trips starting at {where}, "
                    f"about {min_hours:g}–{max_hours:g} hours, ending back there."
                )
            st.caption(rule)

            connect = None
            if continuing and last is not None:
                connect = (clean_token(last["End Location"]), time_to_minutes(last["End Time"]) or 0)

            suggest_full = False
            suggest_round = False
            suggest_next = False
            if continuing:
                suggest_next = st.button(
                    "Suggest next piece",
                    type="primary",
                    use_container_width=True,
                    disabled=not selected_block,
                )
            else:
                button_left, button_right = st.columns(2)
                suggest_full = button_left.button("Suggest full shift", type="primary", use_container_width=True, disabled=not selected_block)
                suggest_round = button_right.button("Suggest round trip", use_container_width=True, disabled=not selected_block)

            if selected_block and (suggest_full or suggest_round or suggest_next):
                mode = "round" if suggest_round or suggest_next else "full"
                built, error = _make_cut(
                    frame,
                    block=selected_block,
                    hub=hub,
                    start_after=start_after,
                    end_by=end_by,
                    min_hours=min_hours,
                    max_hours=max_hours,
                    include_garage=include_garage,
                    mode=mode,
                    connect=connect if suggest_next else None,
                )
                if error:
                    st.session_state["suggestion"] = None
                    st.error(error)
                else:
                    st.session_state["suggestion"] = built

    suggestion = st.session_state.get("suggestion")
    active = suggestion if _suggestion_is_current(suggestion, st.session_state.get("builder_block", ""), include_garage) else None
    suggested_ids = set(active["row_ids"]) if active else set()

    with right:
        with st.container(border=True):
            block_name = st.session_state.get("builder_block") or "—"
            st.markdown(f"**Block {block_name}**")
            if not block_name or block_name == "—":
                st.caption("Choose a block to see its day.")
                table = pd.DataFrame()
            else:
                table = _block_table(frame, block_name, suggested_ids)
                counts = table["Status"].value_counts() if not table.empty else {}
                st.caption(
                    " · ".join(
                        f"{counts.get(name, 0)} {name.lower()}"
                        for name in (OPEN, SUGGESTED, ASSIGNED, GARAGE)
                        if counts.get(name, 0)
                    )
                    or "No trips"
                )
                st.dataframe(_paint(table), use_container_width=True, hide_index=True, height=560)

    if active:
        row_ids = [int(value) for value in active["row_ids"]]
        first = frame.loc[frame["_id"].eq(row_ids[0])].iloc[0]
        last_row = frame.loc[frame["_id"].eq(row_ids[-1])].iloc[0]
        hours = span_hours(frame, row_ids)
        label = propose_label(frame, st.session_state.get("builder_name"))
        warnings = describe_cut(
            frame,
            row_ids,
            str(active.get("hub") or ANY_PLACE),
            float(st.session_state["min_hours"]),
            float(st.session_state["max_hours"]),
            str(active.get("mode") or "full"),
            str(active.get("block")),
        )
        if label_exists(frame, label):
            previous = last_assigned_row(frame, label)
            if previous is not None:
                gap = (time_to_minutes(first["Start Time"]) or 0) - (time_to_minutes(previous["End Time"]) or 0)
                if gap < 0:
                    gap += 24 * 60
                if not same_place(first["Start Location"], previous["End Location"]):
                    warnings.append(
                        f"This piece starts at {clean_token(first['Start Location'])}, "
                        f"and {label} ended at {clean_token(previous['End Location'])}."
                    )
                elif gap < int(st.session_state["min_switch"]):
                    warnings.append(f"Only {gap} minutes to change buses.")
                elif gap > int(st.session_state["max_switch"]):
                    warnings.append(f"{gap} minutes between the last trip and this piece.")
        verb = "Added to" if label_exists(frame, label) else "Saved as"
        st.markdown(
            f"""
            <div class="sam-banner">
                <p class="sam-kicker">Preview · not saved yet</p>
                <h2>{html.escape(format_hours(hours) or "—")}</h2>
                <p>{html.escape(format_time(first['Start Time']))} – {html.escape(format_time(last_row['End Time']))}
                · {len(row_ids)} trips · block {html.escape(str(active['block']))}</p>
                <p>Report at {html.escape(clean_token(first['Start Location']))} at {html.escape(subtract_minutes(first['Start Time'], 15))}</p>
                <p>Routes {html.escape(_route_path(frame, row_ids) or "—")} · {html.escape(verb)} {html.escape(label)}</p>
                {''.join(f'<div class="sam-warn">{html.escape(item)}</div>' for item in warnings)}
            </div>
            """,
            unsafe_allow_html=True,
        )
        preview_rows = _block_table(frame, str(active["block"]), set(row_ids))
        preview_rows = preview_rows.loc[preview_rows["Status"].eq(SUGGESTED), ["Start", "End", "Route", "Dir", "From", "To"]]
        st.dataframe(preview_rows, use_container_width=True, hide_index=True, height=min(420, 48 + 36 * max(len(preview_rows), 1)))
        st.text_input("Note for the packet", key="cut_note", placeholder="Switch bus, break, survey the queue")
        action_a, action_b, action_c = st.columns([1, 1, 2])
        if action_a.button("Shorter", use_container_width=True, disabled=len(row_ids) <= 1):
            active["row_ids"] = row_ids[:-1]
            st.session_state["suggestion"] = active
            st.rerun()
        eligible = [int(value) for value in active["eligible_ids"]]
        can_grow = active["row_ids"][-1] in eligible and eligible.index(int(active["row_ids"][-1])) < len(eligible) - 1
        if action_b.button("Longer", use_container_width=True, disabled=not can_grow):
            position = eligible.index(int(active["row_ids"][-1]))
            active["row_ids"] = [int(value) for value in active["row_ids"]] + [eligible[position + 1]]
            st.session_state["suggestion"] = active
            st.rerun()
        if action_c.button("Save this cut", type="primary", use_container_width=True):
            try:
                _accept(frame, active, label, str(st.session_state.get("cut_note") or ""))
            except Exception as exc:
                st.error(str(exc))
            else:
                st.rerun()
    elif suggestion:
        st.caption("The block or garage setting changed. Suggest the shift again.")

    st.markdown("**Assignments**")
    board_left, board_right = st.columns([1.4, 1])
    with board_left:
        if summary.empty:
            st.caption("Saved shifts will show up here. Select one to keep adding to that person.")
        else:
            st.dataframe(
                summary,
                use_container_width=True,
                hide_index=True,
                height=min(360, 48 + 36 * len(summary)),
                selection_mode="single-row",
                on_select="rerun",
                key="made_table",
            )
            st.caption("Select a row to continue that assignment, or to clear it.")
            selected_label = ""
            if picked and picked[0] < len(summary):
                selected_label = str(summary.iloc[picked[0]]["Assignment"])
            if st.button(
                "Unassign selected assignment",
                disabled=not selected_label,
                use_container_width=True,
            ):
                _unassign(frame, selected_label)
                st.rerun()
        if st.session_state.get("undo") and st.button("Undo last save"):
            _undo(frame)
            st.rerun()
    with board_right:
        st.caption("Notes are printed on the Word packet. The Weekday sheet stays a trip grid.")
        excel = _excel_download(frame)
        st.download_button(
            "Download Weekday workbook",
            data=excel,
            file_name="Weekday.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
        current = clean_token(st.session_state.get("builder_name"))
        if current and label_exists(frame, current):
            packet = _packet_download(frame, current, notes)
            st.download_button(
                f"Download {current}",
                data=packet,
                file_name=f"{_file_piece(current)}.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                use_container_width=True,
            )
        if assigned_labels:
            if st.button("Prepare all Word packets", use_container_width=True):
                try:
                    st.session_state["word_zip"] = packets_zip(frame, notes)
                    st.session_state["word_rev"] = st.session_state.get("revision", 0)
                except Exception as exc:
                    st.error(str(exc))
            if st.session_state.get("word_zip") and st.session_state.get("word_rev") == st.session_state.get("revision", 0):
                st.download_button(
                    "Download all packets",
                    data=st.session_state["word_zip"],
                    file_name="assignment_packets.zip",
                    mime="application/zip",
                    use_container_width=True,
                )
        st.caption("Download the workbook before you close this page. The sheet lives in this session.")


def _excel_download(frame: pd.DataFrame) -> bytes:
    revision = st.session_state.get("revision", 0)
    if st.session_state.get("excel_rev") != revision or not st.session_state.get("excel_bytes"):
        st.session_state["excel_bytes"] = workbook_bytes(frame)
        st.session_state["excel_rev"] = revision
    return st.session_state["excel_bytes"]


def _packet_download(frame: pd.DataFrame, label: str, notes: dict) -> bytes:
    revision = st.session_state.get("revision", 0)
    cache = st.session_state.setdefault("packet_cache", {})
    key = f"{revision}:{label}"
    if key not in cache:
        cache[key] = packet_bytes(frame, label, notes)
    return cache[key]


def _file_piece(label: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in "-_ " else "_" for ch in label).strip()
    return cleaned.replace(" ", "_") or "assignment"


def main() -> None:
    st.set_page_config(page_title=APP_NAME, page_icon=":bus:", layout="wide", initial_sidebar_state="collapsed")
    _inject_css()
    if st.session_state.get("frame") is None:
        _upload_screen()
    else:
        _workspace()


main()
