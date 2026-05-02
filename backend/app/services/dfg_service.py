from pathlib import Path

from app.engines.dfg_engine import calculate_dfg, calculate_variants, calculate_bottlenecks, calculate_summary

PROCESSED_DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "processed"


def get_dfg_graph(dataset_id: str):
    dataset_path = PROCESSED_DATA_DIR / f"{dataset_id}.parquet"
    if not dataset_path.exists():
        raise FileNotFoundError(f"Processed dataset not found for id {dataset_id}")
    return calculate_dfg(str(dataset_path))


def get_variants(dataset_id: str):
    dataset_path = PROCESSED_DATA_DIR / f"{dataset_id}.parquet"
    if not dataset_path.exists():
        raise FileNotFoundError(f"Processed dataset not found for id {dataset_id}")
    return calculate_variants(str(dataset_path))


def get_bottlenecks(dataset_id: str):
    dataset_path = PROCESSED_DATA_DIR / f"{dataset_id}.parquet"
    if not dataset_path.exists():
        raise FileNotFoundError(f"Processed dataset not found for id {dataset_id}")
    return calculate_bottlenecks(str(dataset_path))


def get_summary(dataset_id: str):
    dataset_path = PROCESSED_DATA_DIR / f"{dataset_id}.parquet"
    if not dataset_path.exists():
        raise FileNotFoundError(f"Processed dataset not found for id {dataset_id}")
    return calculate_summary(str(dataset_path))
