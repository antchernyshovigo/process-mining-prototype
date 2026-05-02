import polars as pl
from typing import Any, Dict, List


def calculate_dfg(dataset_path: str) -> Dict[str, List[Dict[str, Any]]]:
    df = pl.read_parquet(dataset_path).select(["case_id", "event_name", "timestamp"])

    expected = {"case_id", "event_name", "timestamp"}
    if not expected.issubset(set(df.columns)):
        raise ValueError("Processed dataset must contain case_id, event_name and timestamp columns")

    df = df.sort(["case_id", "timestamp"])

    case_count = df.select(pl.col("case_id")).unique().height
    node_counts = (
        df.group_by("event_name")
          .agg(pl.count().alias("count"))
          .sort("event_name")
    )

    nodes = [
        {"id": row["event_name"], "count": row["count"]}
        for row in node_counts.iter_rows(named=True)
    ]

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
            "source": row["source_event"],
            "target": row["target_event"],
            "count": row["count"],
            "avg_duration_seconds": float(row["avg_duration_seconds"]),
            "median_duration_seconds": float(row["median_duration_seconds"]),
        }
        for row in edge_groups.iter_rows(named=True)
    ]

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
