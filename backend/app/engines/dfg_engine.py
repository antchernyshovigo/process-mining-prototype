import polars as pl
from typing import Any, Dict, List


def calculate_dfg(dataset_path: str) -> Dict[str, List[Dict[str, Any]]]:
    df = pl.read_parquet(dataset_path).select(["case_id", "event_name", "timestamp"])

    expected = {"case_id", "event_name", "timestamp"}
    if not expected.issubset(set(df.columns)):
        raise ValueError("Processed dataset must contain case_id, event_name and timestamp columns")

    df = df.sort(["case_id", "timestamp"])

    case_count = df.select(pl.col("case_id")).unique().height
    start_groups = (
        df.group_by("case_id")
          .agg(pl.col("event_name").first().alias("event_name"))
          .group_by("event_name")
          .agg(pl.count().alias("count"))
          .sort("event_name")
    )
    end_groups = (
        df.group_by("case_id")
          .agg(pl.col("event_name").last().alias("event_name"))
          .group_by("event_name")
          .agg(pl.count().alias("count"))
          .sort("event_name")
    )

    node_counts = (
        df.group_by("event_name")
          .agg(pl.count().alias("count"))
          .sort("event_name")
    )

    nodes = [{
        "id": "__PROCESS_START__",
        "label": "PROCESS START",
        "count": case_count,
        "type": "start",
    }]
    nodes.extend([
        {"id": row["event_name"], "count": row["count"]}
        for row in node_counts.iter_rows(named=True)
    ])
    nodes.append({
        "id": "__PROCESS_END__",
        "label": "PROCESS END",
        "count": case_count,
        "type": "end",
    })

    transitions = (
        df.with_columns([
            pl.col("event_name").shift(-1).over("case_id").alias("target_event"),
            pl.col("timestamp").shift(-1).over("case_id").alias("target_timestamp"),
            pl.col("timestamp").alias("source_timestamp"),
        ])
        .filter(pl.col("target_event").is_not_null())
        .with_columns(
            (pl.col("target_timestamp") - pl.col("source_timestamp")).dt.total_seconds().alias("duration_seconds")
        )
        .with_columns(
            pl.col("duration_seconds").cast(pl.Float64())
        )
        .select([
            pl.col("event_name").alias("source_event"),
            pl.col("target_event"),
            pl.col("duration_seconds"),
        ])
    )

    all_edges = transitions
    edge_groups = (
        all_edges.group_by(["source_event", "target_event"])
                 .agg([
                     pl.count().alias("count"),
                     pl.col("duration_seconds").mean().alias("avg_duration_seconds"),
                     pl.col("duration_seconds").median().alias("median_duration_seconds"),
                 ])
                 .sort(["source_event", "target_event"])
    )

    edges = [
        {
            "source": "__PROCESS_START__",
            "target": row["event_name"],
            "count": row["count"],
            "avg_duration_seconds": 0.0,
            "median_duration_seconds": 0.0,
        }
        for row in start_groups.iter_rows(named=True)
    ]
    edges.extend([
        {
            "source": row["source_event"],
            "target": row["target_event"],
            "count": row["count"],
            "avg_duration_seconds": float(row["avg_duration_seconds"]),
            "median_duration_seconds": float(row["median_duration_seconds"]),
        }
        for row in edge_groups.iter_rows(named=True)
    ])
    edges.extend([
        {
            "source": row["event_name"],
            "target": "__PROCESS_END__",
            "count": row["count"],
            "avg_duration_seconds": 0.0,
            "median_duration_seconds": 0.0,
        }
        for row in end_groups.iter_rows(named=True)
    ])

    return {"nodes": nodes, "edges": edges}


def calculate_variants(dataset_path: str) -> List[Dict[str, Any]]:
    df = pl.read_parquet(dataset_path).select(["case_id", "event_name", "timestamp"])

    expected = {"case_id", "event_name", "timestamp"}
    if not expected.issubset(set(df.columns)):
        raise ValueError("Processed dataset must contain case_id, event_name and timestamp columns")

    df = df.sort(["case_id", "timestamp"])

    # Собрать последовательность событий для каждого case_id
    variants_df = (
        df.group_by("case_id")
          .agg(pl.col("event_name").str.join(" -> ").alias("variant"))
          .group_by("variant")
          .agg(pl.count().alias("cases_count"))
          .sort("cases_count", descending=True)
    )

    total_cases = variants_df.select(pl.col("cases_count").sum()).item()

    variants = [
        {
            "variant": row["variant"],
            "cases_count": row["cases_count"],
            "share_percent": round((row["cases_count"] / total_cases) * 100, 1),
        }
        for row in variants_df.iter_rows(named=True)
    ]

    return variants


def calculate_bottlenecks(dataset_path: str) -> Dict[str, List[Dict[str, Any]]]:
    df = pl.read_parquet(dataset_path).select(["case_id", "event_name", "timestamp"])

    expected = {"case_id", "event_name", "timestamp"}
    if not expected.issubset(set(df.columns)):
        raise ValueError("Processed dataset must contain case_id, event_name and timestamp columns")

    df = df.sort(["case_id", "timestamp"])

    # Расчет переходов с длительностью
    transitions = (
        df.with_columns([
            pl.col("event_name").shift(-1).over("case_id").alias("target_event"),
            pl.col("timestamp").shift(-1).over("case_id").alias("target_timestamp"),
            pl.col("timestamp").alias("source_timestamp"),
        ])
        .filter(pl.col("target_event").is_not_null())
        .with_columns(
            (pl.col("target_timestamp") - pl.col("source_timestamp")).dt.total_seconds().alias("duration_seconds")
        )
        .with_columns(
            pl.col("duration_seconds").cast(pl.Float64())
        )
        .select([
            pl.col("event_name").alias("source_event"),
            pl.col("target_event"),
            pl.col("duration_seconds"),
        ])
    )

    # Агрегирование по переходам
    edge_groups = (
        transitions.group_by(["source_event", "target_event"])
                   .agg([
                       pl.count().alias("count"),
                       pl.col("duration_seconds").mean().alias("avg_duration_seconds"),
                       pl.col("duration_seconds").median().alias("median_duration_seconds"),
                   ])
    )

    # Форматирование данных
    edge_list = [
        {
            "source": row["source_event"],
            "target": row["target_event"],
            "count": row["count"],
            "avg_duration_seconds": float(row["avg_duration_seconds"]),
            "median_duration_seconds": float(row["median_duration_seconds"]),
        }
        for row in edge_groups.iter_rows(named=True)
    ]

    # Сортировка по avg_duration и median_duration
    top_by_avg = sorted(edge_list, key=lambda x: x["avg_duration_seconds"], reverse=True)
    top_by_median = sorted(edge_list, key=lambda x: x["median_duration_seconds"], reverse=True)

    return {
        "top_by_avg_duration": top_by_avg,
        "top_by_median_duration": top_by_median,
    }


def calculate_time_series(df: pl.DataFrame) -> Dict[str, Dict[str, List[Dict[str, Any]]]]:
    time_buckets = {
        "hour": "1h",
        "day": "1d",
        "week": "1w",
        "month": "1mo",
    }
    case_starts = (
        df.group_by("case_id")
          .agg(pl.col("timestamp").min().alias("start_time"))
    )

    result = {}
    for bucket_name, every in time_buckets.items():
        started_cases = (
            case_starts.with_columns(
                pl.col("start_time").dt.truncate(every).alias("bucket")
            )
            .group_by("bucket")
            .agg(pl.count().alias("started_cases_count"))
            .sort("bucket")
        )
        events = (
            df.with_columns(
                pl.col("timestamp").dt.truncate(every).alias("bucket")
            )
            .group_by("bucket")
            .agg(pl.count().alias("events_count"))
            .sort("bucket")
        )

        result[bucket_name] = {
            "cases_over_time": [
                {
                    "bucket": str(row["bucket"]),
                    "started_cases_count": row["started_cases_count"],
                }
                for row in started_cases.iter_rows(named=True)
            ],
            "events_over_time": [
                {
                    "bucket": str(row["bucket"]),
                    "events_count": row["events_count"],
                }
                for row in events.iter_rows(named=True)
            ],
        }

    return result


def calculate_summary(dataset_path: str) -> Dict[str, Any]:
    df = pl.read_parquet(dataset_path).select(["case_id", "event_name", "timestamp"])

    expected = {"case_id", "event_name", "timestamp"}
    if not expected.issubset(set(df.columns)):
        raise ValueError("Processed dataset must contain case_id, event_name and timestamp columns")

    df = df.sort(["case_id", "timestamp"])

    # Базовые метрики
    events_count = df.height
    cases_count = df.select(pl.col("case_id")).unique().height
    unique_events_count = df.select(pl.col("event_name")).unique().height

    # Уникальные переходы
    transitions = (
        df.with_columns(
            pl.col("event_name").shift(-1).over("case_id").alias("target_event")
        )
        .filter(pl.col("target_event").is_not_null())
        .select(["event_name", "target_event"])
        .unique()
    )
    unique_transitions_count = transitions.height

    # Варианты процесса
    variants_count = (
        df.group_by("case_id")
          .agg(pl.col("event_name").str.join(" -> ").alias("variant"))
          .select(pl.col("variant"))
          .unique()
          .height
    )

    # Временной диапазон
    min_timestamp = df.select(pl.col("timestamp").min()).item()
    max_timestamp = df.select(pl.col("timestamp").max()).item()

    # Длительность случаев
    case_durations = (
        df.group_by("case_id")
          .agg([
              pl.col("timestamp").min().alias("start_time"),
              pl.col("timestamp").max().alias("end_time"),
          ])
          .with_columns(
              (pl.col("end_time") - pl.col("start_time")).dt.total_seconds().cast(pl.Float64()).alias("duration_seconds")
          )
          .select(pl.col("duration_seconds"))
    )

    avg_case_duration_seconds = float(case_durations.select(pl.col("duration_seconds").mean()).item())
    median_case_duration_seconds = float(case_durations.select(pl.col("duration_seconds").median()).item())

    return {
        "events_count": events_count,
        "cases_count": cases_count,
        "unique_events_count": unique_events_count,
        "unique_transitions_count": unique_transitions_count,
        "variants_count": variants_count,
        "min_timestamp": str(min_timestamp),
        "max_timestamp": str(max_timestamp),
        "avg_case_duration_seconds": round(avg_case_duration_seconds, 2),
        "median_case_duration_seconds": round(median_case_duration_seconds, 2),
        "time_series": calculate_time_series(df),
    }
