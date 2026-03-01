"""Step 1 — Fetch project data from Supabase."""

import pandas as pd
from services.supabase_client import get_supabase


def fetch_project_data(
    project_id: str,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    sb = get_supabase()

    project = (
        sb.table("projects")
        .select("id")
        .eq("id", project_id)
        .single()
        .execute()
    )
    if not project.data:
        raise ValueError(f"Project {project_id} not found")

    ts_resp = (
        sb.table("project_timeseries")
        .select("ts, revenue, orders")
        .eq("project_id", project_id)
        .order("ts")
        .execute()
    )
    timeseries = pd.DataFrame(ts_resp.data)

    spend_resp = (
        sb.table("project_spend")
        .select("*")
        .eq("project_id", project_id)
        .order("ts")
        .execute()
    )
    spend = pd.DataFrame(spend_resp.data)

    events_resp = (
        sb.table("project_events")
        .select("event_name, event_type, start_ts, end_ts")
        .eq("project_id", project_id)
        .execute()
    )
    events = pd.DataFrame(events_resp.data)

    return timeseries, spend, events
