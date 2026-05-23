import json
import math
import time
import streamlit as st
import streamlit.components.v1 as components
import requests
import pandas as pd
from io import BytesIO
from pyvis.network import Network
import tempfile

# API базовый URL
API_BASE_URL = "http://127.0.0.1:8000"
PROCESS_START_ID = "__PROCESS_START__"
PROCESS_END_ID = "__PROCESS_END__"

st.set_page_config(page_title="Process Mining Prototype", layout="wide")
st.title("Process Mining Prototype")

# Инициализация session_state
if "dataset_id" not in st.session_state:
    st.session_state.dataset_id = None


def safe_float(value):
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass

    try:
        number = float(value)
    except (TypeError, ValueError):
        return None

    if not math.isfinite(number):
        return None
    return number


def format_number(value):
    number = safe_float(value)
    if number is None:
        return "—"
    if number.is_integer():
        return f"{int(number):,}"
    return f"{number:,.2f}".rstrip("0").rstrip(".")


def format_duration(seconds):
    duration_seconds = safe_float(seconds)
    if duration_seconds is None:
        return "—"

    total_seconds = max(0, int(round(duration_seconds)))
    if total_seconds < 60:
        return f"{total_seconds}s"
    if total_seconds < 3600:
        minutes, seconds = divmod(total_seconds, 60)
        return f"{minutes}m {seconds}s"
    if total_seconds < 86400:
        hours, remainder = divmod(total_seconds, 3600)
        minutes = remainder // 60
        return f"{hours}h {minutes}m"

    days, remainder = divmod(total_seconds, 86400)
    hours = remainder // 3600
    return f"{days}d {hours}h"


def format_timestamp(value):
    if value is None:
        return "—"
    try:
        if pd.isna(value):
            return "—"
    except (TypeError, ValueError):
        pass

    timestamp = pd.to_datetime(value, errors="coerce")
    if pd.isna(timestamp):
        return "—"
    return timestamp.strftime("%Y-%m-%d %H:%M")


def safe_divide(numerator, denominator):
    numerator = safe_float(numerator)
    denominator = safe_float(denominator)
    if numerator is None or denominator is None or denominator == 0:
        return None
    return numerator / denominator


def render_kpi_cards(cards, columns):
    cards_html = "".join(
        f"""
        <div class="process-kpi-card">
            <div class="process-kpi-label">{label}</div>
            <div class="process-kpi-value">{value}</div>
        </div>
        """
        for label, value in cards
    )
    st.markdown(
        f"""
        <div class="process-kpi-grid" style="grid-template-columns: repeat({columns}, minmax(0, 1fr));">
            {cards_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def clean_graph_identifier(value):
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass

    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "null"}:
        return None
    return text


def get_node_id(node):
    for key in ("id", "event_name", "label"):
        node_id = clean_graph_identifier(node.get(key))
        if node_id:
            return node_id
    return None


def normalize_graph_data(nodes, edges):
    normalized_nodes = []
    seen_node_ids = set()
    for node in nodes:
        node_id = get_node_id(node)
        if not node_id or node_id in seen_node_ids:
            continue
        normalized_node = dict(node)
        normalized_node["id"] = node_id
        if node_id == PROCESS_START_ID:
            normalized_node["label"] = "PROCESS START"
            normalized_node["type"] = "start"
        elif node_id == PROCESS_END_ID:
            normalized_node["label"] = "PROCESS END"
            normalized_node["type"] = "end"
        else:
            normalized_node.pop("label", None)
        normalized_nodes.append(normalized_node)
        seen_node_ids.add(node_id)

    normalized_edges = []
    for edge in edges:
        source = clean_graph_identifier(edge.get("source"))
        target = clean_graph_identifier(edge.get("target"))
        if not source or not target:
            continue
        if source not in seen_node_ids or target not in seen_node_ids:
            continue
        normalized_edge = dict(edge)
        normalized_edge["source"] = source
        normalized_edge["target"] = target
        normalized_edges.append(normalized_edge)

    return normalized_nodes, normalized_edges


def render_graph(nodes, edges, mode="process_map", show_edge_labels=True, show_node_counts=True, fullscreen=False):
    nodes, edges = normalize_graph_data(nodes, edges)
    graph_height = "90vh" if fullscreen else "700px"
    graph_width = "100vw" if fullscreen else "100%"
    net = Network(height=graph_height, width=graph_width, directed=True)

    is_process_map = mode == "process_map"
    options = {
        "layout": {
            "hierarchical": {
                "enabled": is_process_map,
                "direction": "LR",
                "sortMethod": "directed",
                "blockShifting": True,
                "edgeMinimization": True,
                "parentCentralization": True,
                "levelSeparation": 280,
                "nodeSpacing": 180,
                "treeSpacing": 240,
            }
        },
        "interaction": {
            "navigationButtons": True,
            "zoomView": True,
            "dragView": True,
            "dragNodes": True,
            "hover": True,
            "keyboard": {"enabled": True},
        },
        "physics": {
            "enabled": not is_process_map,
            "stabilization": {
                "enabled": not is_process_map,
                "iterations": 350,
                "updateInterval": 50,
            },
            "barnesHut": {
                "gravitationalConstant": -26000,
                "centralGravity": 0.2,
                "springLength": 180,
                "springConstant": 0.035,
                "damping": 0.14,
            },
        },
        "nodes": {
            "shape": "box",
            "margin": 16,
            "widthConstraint": {"minimum": 160, "maximum": 320},
            "heightConstraint": {"minimum": 60},
            "font": {
                "size": 15,
                "multi": True,
                "face": "Arial",
            },
        },
        "edges": {
            "smooth": {
                "enabled": True,
                "type": "cubicBezier" if is_process_map else "dynamic",
                "forceDirection": "horizontal" if is_process_map else "none",
                "roundness": 0.55,
            },
            "font": {
                "size": 10,
                "align": "middle",
                "background": "#ffffff",
                "strokeWidth": 4,
                "strokeColor": "#ffffff",
            },
            "color": {
                "color": "#6b7280",
                "highlight": "#2563eb",
                "hover": "#2563eb",
            },
            "selectionWidth": 1.5,
        },
    }
    net.set_options(json.dumps(options))

    node_ids = {str(node["id"]) for node in nodes}
    node_count_by_id = {str(node["id"]): max(0, int(node.get("count", 0))) for node in nodes}
    sources = [str(edge["source"]) for edge in edges]
    adjacency = {}
    for edge in edges:
        source = str(edge["source"])
        target = str(edge["target"])
        adjacency.setdefault(source, []).append(target)

    levels = {}
    if is_process_map:
        start_level_node = PROCESS_START_ID if PROCESS_START_ID in node_ids else None
        queue = []
        if start_level_node:
            levels[start_level_node] = 0
            queue.append(start_level_node)
        else:
            source_candidates = sorted(set(sources) - {str(edge["target"]) for edge in edges})
            for source in source_candidates:
                levels[source] = 0
            queue.extend(source_candidates)

        while queue:
            source = queue.pop(0)
            for target in adjacency.get(source, []):
                if target not in levels:
                    levels[target] = levels[source] + 1
                    queue.append(target)
        for node_id in node_ids:
            levels.setdefault(node_id, 1)
        if PROCESS_END_ID in node_ids:
            max_activity_level = max(
                [level for node_id, level in levels.items() if node_id != PROCESS_END_ID],
                default=1,
            )
            levels[PROCESS_END_ID] = max_activity_level + 1

    for node in nodes:
        node_id = str(node["id"])
        count = node_count_by_id.get(node_id, 0)
        event_name = str(node.get("label", node["id"]))
        label = event_name
        if show_node_counts:
            label = f"{event_name}\ncount: {count}"
        tooltip = f"{event_name}<br>Count: {count}"
        node_options = {"level": levels.get(node_id, 1)} if is_process_map else {}
        if node_id == PROCESS_START_ID:
            net.add_node(
                node_id,
                label="PROCESS\nSTART",
                shape="ellipse",
                title=tooltip,
                color={"background": "#dcfce7", "border": "#16a34a", "highlight": {"background": "#bbf7d0", "border": "#15803d"}},
                font={"size": 14, "face": "Arial", "bold": True},
                widthConstraint={"minimum": 120, "maximum": 180},
                heightConstraint={"minimum": 58},
                **node_options,
            )
        elif node_id == PROCESS_END_ID:
            net.add_node(
                node_id,
                label="PROCESS\nEND",
                shape="ellipse",
                title=tooltip,
                color={"background": "#fee2e2", "border": "#dc2626", "highlight": {"background": "#fecaca", "border": "#b91c1c"}},
                font={"size": 14, "face": "Arial", "bold": True},
                widthConstraint={"minimum": 120, "maximum": 180},
                heightConstraint={"minimum": 58},
                **node_options,
            )
        else:
            net.add_node(
                node_id,
                label=label,
                shape="box",
                title=tooltip,
                color={"background": "#e8f2ff", "border": "#3b82f6", "highlight": {"background": "#dbeafe", "border": "#2563eb"}},
                widthConstraint={"minimum": 160, "maximum": 320},
                heightConstraint={"minimum": 60},
                **node_options,
            )

    for edge in edges:
        source = str(edge["source"])
        target = str(edge["target"])
        count = int(edge.get("count", 0))
        width = min(8, 1 + math.log(count + 1))
        label = str(count) if show_edge_labels else ""
        avg_duration = float(edge.get("avg_duration_seconds", 0))
        title = f"{source} -> {target}<br>count: {count}<br>avg duration: {avg_duration:.1f}s"
        edge_color = "#16a34a" if source == PROCESS_START_ID else None
        if target == PROCESS_END_ID:
            edge_color = "#dc2626"
        edge_kwargs = {"color": edge_color} if edge_color else {}
        net.add_edge(
            source,
            target,
            label=label,
            title=title,
            width=width,
            arrows="to",
            font={"size": 10, "align": "middle", "background": "#ffffff", "strokeWidth": 4, "strokeColor": "#ffffff"},
            **edge_kwargs,
        )

    with tempfile.NamedTemporaryFile(delete=False, suffix=".html") as tmp_file:
        net.write_html(tmp_file.name)
        tmp_file_path = tmp_file.name

    with open(tmp_file_path, "r", encoding="utf-8") as f:
        html = f.read()

    fullscreen_flag = "true" if fullscreen else "false"
    injection = """
<script type=\"text/javascript\">
(function() {
    var isFullscreen = __FULLSCREEN__;

    function addGraphToolbar(network) {
        var toolbar = document.createElement('div');
        toolbar.style.position = 'absolute';
        toolbar.style.top = '14px';
        toolbar.style.right = '14px';
        toolbar.style.zIndex = 9999;
        toolbar.style.display = 'flex';
        toolbar.style.gap = '8px';
        toolbar.style.padding = '8px';
        toolbar.style.backgroundColor = 'rgba(255, 255, 255, 0.92)';
        toolbar.style.border = '1px solid #d8dee9';
        toolbar.style.borderRadius = '8px';
        toolbar.style.boxShadow = '0 2px 10px rgba(15, 23, 42, 0.16)';

        function makeButton(label, handler) {
            var btn = document.createElement('button');
            btn.innerText = label;
            btn.style.padding = '8px 10px';
            btn.style.backgroundColor = '#1976d2';
            btn.style.color = '#ffffff';
            btn.style.border = 'none';
            btn.style.borderRadius = '6px';
            btn.style.cursor = 'pointer';
            btn.style.fontSize = '12px';
            btn.style.fontWeight = '600';
            btn.onclick = handler;
            return btn;
        }

        toolbar.appendChild(makeButton('FIT', function() {
            network.fit({ animation: { duration: 700, easingFunction: 'easeInOutQuad' } });
        }));
        toolbar.appendChild(makeButton('CENTER', function() {
            network.moveTo({ position: { x: 0, y: 0 }, scale: network.getScale(), animation: { duration: 500 } });
        }));
        toolbar.appendChild(makeButton('+', function() {
            network.moveTo({ scale: network.getScale() * 1.2, animation: { duration: 250 } });
        }));
        toolbar.appendChild(makeButton('-', function() {
            network.moveTo({ scale: network.getScale() / 1.2, animation: { duration: 250 } });
        }));

        document.body.style.position = 'relative';
        document.body.style.margin = '0';
        document.body.style.overflow = isFullscreen ? 'hidden' : 'auto';
        document.body.appendChild(toolbar);
    }

    function centerNetwork(network) {
        if (typeof network !== 'undefined') {
            network.fit({ animation: { duration: 800, easingFunction: 'easeInOutQuad' } });
            if (typeof network.redraw === 'function') {
                network.redraw();
            }
        }
    }

    document.addEventListener('DOMContentLoaded', function() {
        var graphContainer = document.getElementById('mynetwork');
        if (graphContainer && isFullscreen) {
            graphContainer.style.width = '100vw';
            graphContainer.style.height = '90vh';
            graphContainer.style.border = 'none';
        }
        if (typeof network !== 'undefined') {
            addGraphToolbar(network);
            network.once('afterDrawing', function() {
                centerNetwork(network);
            });
            setTimeout(function() {
                centerNetwork(network);
            }, 500);
            if (network.physics && network.physics.options && network.physics.options.enabled) {
                network.once('stabilizationIterationsDone', function() {
                    centerNetwork(network);
                });
            }
        }
    });
})();
</script>
"""

    injection = injection.replace("__FULLSCREEN__", fullscreen_flag)
    html = html.replace('</body>', injection + '</body>')
    return html
page = st.sidebar.radio(
    "Navigation",
    ["Upload", "Summary", "Graph", "Variants", "Bottlenecks"],
    index=0,
)

st.sidebar.header("Dataset")
if st.session_state.dataset_id:
    st.sidebar.success(f"Active: {st.session_state.dataset_id}")
else:
    st.sidebar.info("No dataset selected")

if st.sidebar.button("Clear dataset"):
    st.session_state.dataset_id = None
    st.rerun()


def update_progress(progress_placeholder, percent, stage, start_ts):
    elapsed = int(time.perf_counter() - start_ts)
    progress_placeholder.markdown(
        f"**Stage:** {stage}  \n"
        f"**Elapsed:** {elapsed}s  \n"
        f"**Progress:** {percent}%"
    )


if page == "Upload":
    st.header("Upload Dataset")
    uploaded_file = st.file_uploader("Choose CSV or Excel file", type=["csv", "xlsx"])

    preview_df = None
    columns = []
    delimiter = None
    upload_feedback = st.empty()
    progress_placeholder = st.empty()
    progress_bar = st.progress(0)

    if uploaded_file is not None:
        st.write(f"**File:** {uploaded_file.name}")
        file_size = getattr(uploaded_file, "size", None)
        if file_size and file_size > 500 * 1024 * 1024:
            st.warning("Large file selected. Upload may take some time.")

        if uploaded_file.name.lower().endswith(".csv"):
            delimiter_options = {
                "Auto": "auto",
                "Comma (,)": ",",
                "Semicolon (;)": ";",
                "Tab (\t)": "\t",
                "Pipe (|)": "|",
            }
            delimiter_choice = st.selectbox(
                "Delimiter",
                list(delimiter_options.keys()),
                index=0,
                help="Choose the delimiter for CSV files or leave Auto for autodetection.",
            )
            delimiter = delimiter_options[delimiter_choice]

        try:
            uploaded_file.seek(0)
            if uploaded_file.name.lower().endswith(".csv"):
                if delimiter == "auto":
                    preview_df = pd.read_csv(uploaded_file, nrows=20, sep=None, engine="python")
                else:
                    preview_df = pd.read_csv(uploaded_file, nrows=20, sep=delimiter)
            else:
                preview_df = pd.read_excel(uploaded_file, nrows=20)
            uploaded_file.seek(0)
            st.success("Preview loaded")
        except Exception as e:
            preview_df = None
            st.error(f"Preview failed: {str(e)}")

        if preview_df is not None:
            st.subheader("Preview")
            st.dataframe(preview_df, use_container_width=True)

            columns = list(preview_df.columns)
            detected_columns = []
            for col in columns:
                values = preview_df[col]
                sample = ""
                non_null_count = int(values.notnull().sum())
                if non_null_count > 0:
                    sample = str(values.dropna().iloc[0])
                detected_columns.append(
                    {
                        "column_name": col,
                        "detected_dtype": str(values.dtype),
                        "non_null_preview_count": non_null_count,
                        "sample_value": sample,
                    }
                )

            st.subheader("Detected Columns")
            st.dataframe(pd.DataFrame(detected_columns), use_container_width=True)

            def find_default_column(candidates):
                lower_map = {col.lower(): col for col in columns}
                for candidate in candidates:
                    if candidate in lower_map:
                        return lower_map[candidate]
                return columns[0] if columns else ""

            case_id_default = find_default_column(["case_id", "caseid", "case", "id", "user_id"])
            event_name_default = find_default_column(["event_name", "event", "activity", "task", "step"])
            timestamp_default = find_default_column(["timestamp", "time", "date", "datetime", "ts"])

            st.subheader("Column Mapping")
            case_id_column = st.selectbox(
                "Case ID Column",
                columns,
                index=columns.index(case_id_default) if case_id_default in columns else 0,
                key="case_id_input",
            )
            event_name_column = st.selectbox(
                "Event Name Column",
                columns,
                index=columns.index(event_name_default) if event_name_default in columns else 0,
                key="event_name_input",
            )
            timestamp_column = st.selectbox(
                "Timestamp Column",
                columns,
                index=columns.index(timestamp_default) if timestamp_default in columns else 0,
                key="timestamp_input",
            )

            if st.button("Upload Dataset", key="upload_btn"):
                if not case_id_column or not event_name_column or not timestamp_column:
                    st.error("Please select all mapping columns before uploading.")
                else:
                    start_ts = time.perf_counter()
                    update_progress(progress_placeholder, 0, "Preparing upload", start_ts)
                    try:
                        uploaded_file.seek(0)
                        file_size = getattr(uploaded_file, "size", None)
                        content_type = getattr(uploaded_file, "type", None)
                        if file_size is None:
                            file_bytes = uploaded_file.read()
                            file_size = len(file_bytes)
                            new_file = BytesIO(file_bytes)
                            new_file.name = getattr(uploaded_file, "name", "uploaded_file")
                            if content_type is not None:
                                new_file.type = content_type
                            uploaded_file = new_file
                        else:
                            uploaded_file.seek(0)

                        use_chunk_upload = (
                            uploaded_file.name.lower().endswith(".csv")
                            and file_size is not None
                            and file_size > 200 * 1024 * 1024
                        )

                        if use_chunk_upload:
                            update_progress(progress_placeholder, 10, "Starting chunked upload", start_ts)
                            upload_feedback.info("Starting chunked upload...")
                            payload = {
                                "filename": uploaded_file.name,
                                "file_size": file_size,
                                "case_id_column": case_id_column,
                                "event_name_column": event_name_column,
                                "timestamp_column": timestamp_column,
                                "delimiter": delimiter or "auto",
                            }
                            start_resp = requests.post(
                                f"{API_BASE_URL}/uploads/start",
                                json=payload,
                            )

                            if start_resp.status_code != 200:
                                error_detail = start_resp.json().get("detail", start_resp.text)
                                st.error(f"Chunked upload failed to start: {error_detail}")
                            else:
                                upload_id = start_resp.json()["upload_id"]
                                total_chunks = math.ceil(file_size / (10 * 1024 * 1024))
                                uploaded_file.seek(0)
                                chunk_index = 1
                                while True:
                                    chunk_bytes = uploaded_file.read(10 * 1024 * 1024)
                                    if not chunk_bytes:
                                        break
                                    update_progress(
                                        progress_placeholder,
                                        int((chunk_index / total_chunks) * 100 * 0.8) + 10,
                                        f"Uploading chunk {chunk_index}/{total_chunks}",
                                        start_ts,
                                    )
                                    chunk_response = requests.post(
                                        f"{API_BASE_URL}/uploads/{upload_id}/chunk",
                                        data={
                                            "chunk_index": chunk_index,
                                            "total_chunks": total_chunks,
                                        },
                                        files={
                                            "chunk": (
                                                f"chunk_{chunk_index}",
                                                chunk_bytes,
                                                "application/octet-stream",
                                            )
                                        },
                                    )
                                    if chunk_response.status_code != 200:
                                        error_detail = chunk_response.json().get("detail", chunk_response.text)
                                        raise ValueError(
                                            f"Chunk {chunk_index} upload failed: {error_detail}"
                                        )
                                    progress_bar.progress(
                                        min(100, int((chunk_index / total_chunks) * 100))
                                    )
                                    chunk_index += 1

                                update_progress(progress_placeholder, 95, "Finalizing upload", start_ts)
                                upload_feedback.info("Finalizing upload...")
                                complete_resp = requests.post(
                                    f"{API_BASE_URL}/uploads/{upload_id}/complete"
                                )
                                if complete_resp.status_code == 200:
                                    result = complete_resp.json()
                                    st.session_state.dataset_id = result["dataset_id"]
                                    update_progress(progress_placeholder, 100, "Upload complete", start_ts)
                                    st.success(f"Dataset uploaded! ID: {result['dataset_id']}")
                                    st.write(f"Rows (raw): {result['rows_count_raw']}")
                                    st.write(f"Rows (processed): {result['rows_count_processed']}")
                                    st.rerun()
                                else:
                                    error_detail = complete_resp.json().get("detail", complete_resp.text)
                                    st.error(f"Upload complete failed: {error_detail}")
                        else:
                            update_progress(progress_placeholder, 20, "Uploading dataset", start_ts)
                            upload_feedback.info("Uploading dataset...")
                            files = {"file": (uploaded_file.name, uploaded_file, uploaded_file.type)}
                            data = {
                                "case_id_column": case_id_column,
                                "event_name_column": event_name_column,
                                "timestamp_column": timestamp_column,
                            }
                            if delimiter is not None:
                                data["delimiter"] = delimiter

                            response = requests.post(
                                f"{API_BASE_URL}/datasets/upload",
                                files=files,
                                data=data,
                            )
                            progress_bar.progress(70)

                            if response.status_code == 200:
                                result = response.json()
                                st.session_state.dataset_id = result["dataset_id"]
                                update_progress(progress_placeholder, 100, "Upload complete", start_ts)
                                st.success(f"Dataset uploaded! ID: {result['dataset_id']}")
                                st.write(f"Rows (raw): {result['rows_count_raw']}")
                                st.write(f"Rows (processed): {result['rows_count_processed']}")
                                st.rerun()
                            else:
                                error_detail = response.json().get("detail", response.text)
                                st.error(f"Upload failed: {error_detail}")
                    except Exception as e:
                        st.error(f"Error uploading file: {str(e)}")
        else:
            st.info("Waiting for a valid preview to be generated before upload.")
    else:
        st.info("Select a CSV or Excel file to begin.")

elif page == "Summary":
    st.header("Process Overview")
    st.markdown(
        """
        <style>
            .process-overview-subtitle {
                color: #6b7280;
                font-size: 15px;
                margin: -4px 0 18px 0;
            }
            .process-kpi-grid {
                display: grid;
                gap: 14px;
                margin: 12px 0 18px 0;
            }
            .process-kpi-card {
                background: #ffffff;
                border: 1px solid #e5e7eb;
                border-radius: 12px;
                box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
                min-height: 96px;
                padding: 18px;
            }
            .process-kpi-label {
                color: #6b7280;
                font-size: 12px;
                font-weight: 650;
                letter-spacing: 0;
                line-height: 1.25;
                margin-bottom: 10px;
            }
            .process-kpi-value {
                color: #111827;
                font-size: 28px;
                font-weight: 800;
                line-height: 1.1;
                overflow-wrap: anywhere;
            }
            .process-summary-panel {
                background: #ffffff;
                border: 1px solid #e5e7eb;
                border-radius: 12px;
                margin-top: 12px;
                padding: 18px;
            }
            .process-summary-panel-title {
                color: #111827;
                font-size: 16px;
                font-weight: 750;
                margin-bottom: 10px;
            }
            .process-summary-list {
                color: #374151;
                font-size: 15px;
                line-height: 1.55;
                margin: 0;
                padding-left: 20px;
            }
        </style>
        <p class="process-overview-subtitle">
            High-level view of the uploaded event log and process behavior.
        </p>
        """,
        unsafe_allow_html=True,
    )
    if not st.session_state.dataset_id:
        st.info("Upload a dataset first to see summary data.")
    else:
        dataset_id = st.session_state.dataset_id
        try:
            response = requests.get(f"{API_BASE_URL}/datasets/{dataset_id}/summary")
            if response.status_code == 200:
                summary = response.json()
                events_count = summary.get("events_count")
                cases_count = summary.get("cases_count")
                activities_count = summary.get("unique_events_count")
                transitions_count = summary.get("unique_transitions_count")
                variants_count = summary.get("variants_count")
                avg_duration = summary.get("avg_case_duration_seconds")
                median_duration = summary.get("median_case_duration_seconds")
                min_timestamp = summary.get("min_timestamp")
                max_timestamp = summary.get("max_timestamp")

                events_per_case = safe_divide(events_count, cases_count)
                variants_per_100_cases = None
                variants_per_case = safe_divide(variants_count, cases_count)
                if variants_per_case is not None:
                    variants_per_100_cases = variants_per_case * 100

                render_kpi_cards(
                    [
                        ("Events", format_number(events_count)),
                        ("Cases", format_number(cases_count)),
                        ("Activities", format_number(activities_count)),
                        ("Transitions", format_number(transitions_count)),
                        ("Variants", format_number(variants_count)),
                    ],
                    columns=5,
                )
                render_kpi_cards(
                    [
                        ("Avg case duration", format_duration(avg_duration)),
                        ("Median case duration", format_duration(median_duration)),
                        ("Events per case", format_number(events_per_case)),
                        ("Variants per 100 cases", format_number(variants_per_100_cases)),
                    ],
                    columns=4,
                )

                st.subheader("Process variability")
                if variants_per_case is None:
                    st.info("Not enough data to assess process variability.")
                elif variants_per_case > 0.3:
                    st.warning("High variability: many unique variants compared to total cases.")
                else:
                    st.success("Process variants are relatively concentrated.")

                start_time = pd.to_datetime(min_timestamp, errors="coerce")
                end_time = pd.to_datetime(max_timestamp, errors="coerce")
                covered_period = "—"
                if not pd.isna(start_time) and not pd.isna(end_time):
                    covered_seconds = (end_time - start_time).total_seconds()
                    if covered_seconds >= 0:
                        covered_period = format_duration(covered_seconds)

                st.subheader("Time period")
                render_kpi_cards(
                    [
                        ("Start", format_timestamp(min_timestamp)),
                        ("End", format_timestamp(max_timestamp)),
                        ("Covered period", covered_period),
                    ],
                    columns=3,
                )

                interpretations = []
                if events_per_case is not None:
                    interpretations.append(f"Average case contains {format_number(events_per_case)} events.")
                if variants_count is not None and cases_count is not None:
                    interpretations.append(
                        f"There are {format_number(variants_count)} variants across {format_number(cases_count)} cases."
                    )
                avg_duration_number = safe_float(avg_duration)
                median_duration_number = safe_float(median_duration)
                if (
                    avg_duration_number is not None
                    and median_duration_number is not None
                    and median_duration_number > 0
                    and avg_duration_number > median_duration_number * 3
                ):
                    interpretations.append("Median duration is much lower than average.")
                if not interpretations:
                    interpretations.append("Upload contains limited summary data, so interpretation is not available yet.")

                interpretation_items = "".join(f"<li>{item}</li>" for item in interpretations)
                st.markdown(
                    f"""
                    <div class="process-summary-panel">
                        <div class="process-summary-panel-title">Quick interpretation</div>
                        <ul class="process-summary-list">{interpretation_items}</ul>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            else:
                st.error(f"Error: {response.json().get('detail', response.text)}")
        except Exception as e:
            st.error(f"Error fetching summary: {str(e)}")

elif page == "Graph":
    st.header("Process Graph")
    if not st.session_state.dataset_id:
        st.info("Upload a dataset first to see the process graph.")
    else:
        dataset_id = st.session_state.dataset_id
        try:
            response = requests.get(f"{API_BASE_URL}/datasets/{dataset_id}/graph")
            if response.status_code == 200:
                graph = response.json()
                graph_nodes, graph_edges = normalize_graph_data(graph["nodes"], graph["edges"])
                nodes_df = pd.DataFrame(graph_nodes)
                edges_df = pd.DataFrame(graph_edges)
                total_edges = len(edges_df)
                large_graph = total_edges > 100

                st.subheader("Graph Controls")
                col1, col2, col3 = st.columns(3)
                col4, col5, col6, col7 = st.columns(4)

                min_transition_count = col1.number_input(
                    "Min Transition Count",
                    min_value=1,
                    value=1,
                    step=1,
                )
                top_n_transitions = col2.slider("Top N Transitions", 5, 200, 30)
                top_n_activities = col3.slider("Top N Activities", 5, 200, 30)
                show_edge_labels = col4.checkbox("Show edge labels", value=True)
                show_node_counts = col5.checkbox("Show node counts", value=True)
                graph_mode = col6.selectbox("Layout Mode", ["Process Map", "Free Layout"])
                fullscreen_graph = col7.checkbox("Fullscreen graph", value=False)

                if large_graph:
                    st.info("Large graph detected — low-frequency transitions are hidden by default.")
                    min_transition_count = max(min_transition_count, 2)

                synthetic_node_ids = {PROCESS_START_ID, PROCESS_END_ID}
                raw_edges_count = len(edges_df)
                raw_regular_nodes_count = 0

                if not nodes_df.empty:
                    nodes_df["id"] = nodes_df["id"].astype(str)
                    synthetic_nodes_df = nodes_df[nodes_df["id"].isin(synthetic_node_ids)]
                    regular_nodes_df = nodes_df[~nodes_df["id"].isin(synthetic_node_ids)]
                    raw_regular_nodes_count = len(regular_nodes_df)
                    regular_nodes_df = regular_nodes_df.sort_values("count", ascending=False).head(top_n_activities)
                    nodes_df = pd.concat([synthetic_nodes_df, regular_nodes_df], ignore_index=True)

                visible_node_ids = set(nodes_df["id"].astype(str).tolist()) if not nodes_df.empty else set()

                if not edges_df.empty:
                    edges_df["source"] = edges_df["source"].astype(str)
                    edges_df["target"] = edges_df["target"].astype(str)
                    edges_df = edges_df[edges_df["count"] >= min_transition_count]
                    edges_df = edges_df.nlargest(top_n_transitions, "count")
                    edges_df = edges_df[
                        edges_df["source"].isin(visible_node_ids) &
                        edges_df["target"].isin(visible_node_ids)
                    ]

                hidden_edges_count = raw_edges_count - len(edges_df)
                visible_activities_count = len(nodes_df[~nodes_df["id"].isin(synthetic_node_ids)]) if not nodes_df.empty else 0
                hidden_nodes_count = max(0, raw_regular_nodes_count - visible_activities_count)
                graph_message = f"Showing {visible_activities_count} activities and {len(edges_df)} transitions"
                if hidden_edges_count > 0 or hidden_nodes_count > 0:
                    graph_message += ". Some low-frequency elements are hidden."
                st.caption(graph_message)

                if edges_df.empty:
                    st.warning("No edges remain after filtering. Relax filters to view the graph.")
                else:
                    if not fullscreen_graph:
                        st.subheader("Nodes")
                        st.dataframe(nodes_df, use_container_width=True)
                        st.subheader("Edges")
                        st.dataframe(edges_df, use_container_width=True)
                    try:
                        mode_value = "free" if graph_mode == "Free Layout" else "process_map"
                        graph_html = render_graph(
                            nodes_df.to_dict("records"),
                            edges_df.to_dict("records"),
                            mode=mode_value,
                            show_edge_labels=show_edge_labels,
                            show_node_counts=show_node_counts,
                            fullscreen=fullscreen_graph,
                        )
                        graph_height = 1000 if fullscreen_graph else 650
                        components.html(graph_html, height=graph_height, scrolling=not fullscreen_graph)
                    except Exception as e:
                        st.error(f"Error rendering graph: {str(e)}")
            else:
                st.error(f"Error: {response.json().get('detail', response.text)}")
        except Exception as e:
            st.error(f"Error fetching graph: {str(e)}")

elif page == "Variants":
    st.header("Process Variants")
    if not st.session_state.dataset_id:
        st.info("Upload a dataset first to see variants.")
    else:
        dataset_id = st.session_state.dataset_id
        try:
            response = requests.get(f"{API_BASE_URL}/datasets/{dataset_id}/variants")
            if response.status_code == 200:
                variants = response.json()
                variants_df = pd.DataFrame(variants)
                st.dataframe(variants_df, use_container_width=True)
            else:
                st.error(f"Error: {response.json().get('detail', response.text)}")
        except Exception as e:
            st.error(f"Error fetching variants: {str(e)}")

elif page == "Bottlenecks":
    st.header("Bottlenecks Analysis")
    if not st.session_state.dataset_id:
        st.info("Upload a dataset first to see bottlenecks.")
    else:
        dataset_id = st.session_state.dataset_id
        try:
            response = requests.get(f"{API_BASE_URL}/datasets/{dataset_id}/bottlenecks")
            if response.status_code == 200:
                bottlenecks = response.json()
                st.subheader("Top by Avg Duration")
                avg_df = pd.DataFrame(bottlenecks["top_by_avg_duration"]).head(25)
                st.dataframe(avg_df, use_container_width=True)

                st.subheader("Top by Median Duration")
                median_df = pd.DataFrame(bottlenecks["top_by_median_duration"]).head(25)
                st.dataframe(median_df, use_container_width=True)
            else:
                st.error(f"Error: {response.json().get('detail', response.text)}")
        except Exception as e:
            st.error(f"Error fetching bottlenecks: {str(e)}")
    

                
