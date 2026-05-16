# Process Mining Prototype

A lightweight process mining prototype for uploading event logs, normalizing them, building a directly-follows graph, and exploring summary metrics, variants, and bottlenecks in a Streamlit UI.

## Features

- Upload CSV event logs through the UI.
- Preview uploaded files and map event log columns.
- Normalize data into standard columns: `case_id`, `event_name`, `timestamp`.
- Build a directly-follows graph (DFG).
- View process variants and bottleneck transitions.
- Use regular upload for small files and chunked upload for large CSV files.

## Project Structure

```text
backend/
  app/
    api/          FastAPI routes
    engines/      Process mining calculations
    services/     Dataset and upload services
  data/
    raw/          Uploaded source files
    processed/    Normalized parquet datasets
ui/
  streamlit_app.py
data/
  sample/
    event_log.csv
```

## Quick Start

Run backend and UI in separate terminals.

### Backend

```bash
cd backend
source venv/bin/activate
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Backend URLs:

- API base: `http://127.0.0.1:8000`
- Health check: `http://127.0.0.1:8000/health`

### UI

```bash
cd ui
source venv/bin/activate
streamlit run streamlit_app.py --server.address 127.0.0.1 --server.port 8501
```

UI URL:

- `http://127.0.0.1:8501`

## Event Log Format

The app expects an event log with at least three columns:

```csv
case_id,event_name,timestamp
1,Start,2026-01-01 10:00:00
1,Check,2026-01-01 10:05:00
1,Approve,2026-01-01 10:10:00
```

Column names do not have to match exactly. During upload, map your file columns to:

- Case ID column
- Event name column
- Timestamp column

A sample file is available at:

```text
data/sample/event_log.csv
```

## Using The App

1. Start backend on `8000`.
2. Start UI on `8501`.
3. Open `http://127.0.0.1:8501`.
4. Upload a CSV file.
5. Confirm delimiter and column mapping.
6. Explore:
   - Summary
   - Graph
   - Variants
   - Bottlenecks

## API Endpoints

Main dataset endpoints:

- `POST /datasets/upload`
- `GET /datasets/{dataset_id}/summary`
- `GET /datasets/{dataset_id}/graph`
- `GET /datasets/{dataset_id}/variants`
- `GET /datasets/{dataset_id}/bottlenecks`

Chunked upload endpoints:

- `POST /uploads/start`
- `POST /uploads/{upload_id}/chunk`
- `POST /uploads/{upload_id}/complete`
- `GET /uploads/{upload_id}/status`

## Notes

- The UI is configured to call backend at `http://127.0.0.1:8000`.
- Generated files in `backend/data/raw`, `backend/data/processed`, and `backend/data/uploads` are runtime data.
- Python cache files (`__pycache__`) are runtime artifacts and should not be committed.
- Excel upload is visible in the UI, but backend Excel reading requires the optional Polars Excel dependency (`fastexcel`) to be installed.

## Sanity Checks

Compile UI:

```bash
ui/venv/bin/python -m py_compile ui/streamlit_app.py
```

Check backend health:

```bash
curl http://127.0.0.1:8000/health
```
