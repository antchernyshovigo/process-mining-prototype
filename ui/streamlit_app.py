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

st.set_page_config(page_title="Process Mining Prototype", layout="wide")
st.title("Process Mining Prototype")

# Инициализация session_state
if "dataset_id" not in st.session_state:
    st.session_state.dataset_id = None


def render_graph(nodes, edges, mode="hierarchical", show_edge_labels=True, show_node_counts=True):
    net = Network(height="600px", width="100%", directed=True)

    options = {
        "layout": {
            "hierarchical": {
                "enabled": True,
                "direction": "LR",
                "sortMethod": "hubsize",
                "edgeMinimization": True,
                "levelSeparation": 260,
                "nodeSpacing": 220,
                "treeSpacing": 260,
            }
        },
        "interaction": {
            "navigationButtons": True,
            "zoomView": True,
        },
        "physics": {
            "enabled": False,
        },
        "nodes": {
            "shape": "box",
            "margin": 16,
            "widthConstraint": {"minimum": 150, "maximum": 280},
            "heightConstraint": {"minimum": 55},
        },
        "edges": {
            "smooth": {
                "type": "cubicBezier",
                "forceDirection": "horizontal",
                "roundness": 0.45,
            }
        },
    }
    net.set_options(json.dumps(options))

    node_ids = {node["id"] for node in nodes}
    node_count_by_id = {node["id"]: max(0, int(node.get("count", 0))) for node in nodes}
    sources = [edge["source"] for edge in edges]

    for node in nodes:
        count = node_count_by_id.get(node["id"], 0)
        event_name = str(node["id"])
        label = event_name
        if show_node_counts:
            label = f"{event_name}\ncount: {count}"
        tooltip = f"{event_name}<br>Count: {count}"
        net.add_node(
            node["id"],
            label=label,
            shape="box",
            title=tooltip,
            color="#97C2FC",
            widthConstraint={"minimum": 150, "maximum": 280},
            heightConstraint={"minimum": 55},
        )

    for edge in edges:
        count = int(edge.get("count", 0))
        width = min(8, 1 + math.log(count + 1))
        label = str(count) if show_edge_labels else ""
        avg_duration = float(edge.get("avg_duration_seconds", 0))
        title = f"{edge['source']} --{count}--> {edge['target']}<br>Avg duration: {avg_duration:.1f}s"
        net.add_edge(
            edge["source"],
            edge["target"],
            label=label,
            title=title,
            width=width,
            arrows="to",
        )

    end_nodes = [nid for nid in node_ids if nid not in sources]

    if "END" not in node_ids and end_nodes:
        net.add_node("END", label="END", color="#aa0000", size=36, shape="ellipse")
        for source in end_nodes:
            net.add_edge(source, "END", label="end", width=2, arrows="to")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".html") as tmp_file:
        net.write_html(tmp_file.name)
        tmp_file_path = tmp_file.name

    with open(tmp_file_path, "r", encoding="utf-8") as f:
        html = f.read()

    injection = """
<script type=\"text/javascript\">
(function() {
    function addCenterGraphButton(network) {
        var btn = document.createElement('button');
        btn.innerText = 'CENTER / FIT';
        btn.style.position = 'absolute';
        btn.style.top = '16px';
        btn.style.right = '16px';
        btn.style.zIndex = 9999;
        btn.style.padding = '10px 16px';
        btn.style.backgroundColor = '#1976d2';
        btn.style.color = '#ffffff';
        btn.style.border = 'none';
        btn.style.borderRadius = '6px';
        btn.style.cursor = 'pointer';
        btn.style.boxShadow = '0 2px 8px rgba(0, 0, 0, 0.2)';
        btn.onclick = function() {
            if (typeof network !== 'undefined') {
                network.fit({ animation: { duration: 800, easingFunction: 'easeInOutQuad' } });
            }
        };
        document.body.style.position = 'relative';
        document.body.appendChild(btn);
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
        if (typeof network !== 'undefined') {
            addCenterGraphButton(network);
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
    st.header("Summary Metrics")
    if not st.session_state.dataset_id:
        st.info("Upload a dataset first to see summary data.")
    else:
        dataset_id = st.session_state.dataset_id
        try:
            response = requests.get(f"{API_BASE_URL}/datasets/{dataset_id}/summary")
            if response.status_code == 200:
                summary = response.json()
                col1, col2, col3, col4, col5 = st.columns(5)
                col1.metric("Events", summary["events_count"])
                col2.metric("Cases", summary["cases_count"])
                col3.metric("Unique Events", summary["unique_events_count"])
                col4.metric("Unique Transitions", summary["unique_transitions_count"])
                col5.metric("Variants", summary["variants_count"])

                col1, col2 = st.columns(2)
                col1.metric("Avg Case Duration (sec)", round(summary["avg_case_duration_seconds"], 2))
                col2.metric("Median Case Duration (sec)", round(summary["median_case_duration_seconds"], 2))

                st.write(f"**Min Timestamp:** {summary['min_timestamp']}")
                st.write(f"**Max Timestamp:** {summary['max_timestamp']}")
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
                graph_mode = st.radio("Graph Layout Mode", ["Hierarchical", "Force"], horizontal=True)
                min_transition_count = st.slider("Min Transition Count", 1, 20, 1)
                top_n_edges = st.slider("Top N Edges", 5, 100, 25)
                show_edge_labels = st.checkbox("Show edge labels", value=True)
                show_node_counts = st.checkbox("Show node counts", value=True)
                if st.button("Zoom to Fit"):
                    st.rerun()

                nodes_df = pd.DataFrame(graph["nodes"])
                edges_df = pd.DataFrame(graph["edges"])
                total_edges = len(edges_df)
                if total_edges > 100 and min_transition_count < 2:
                    min_transition_count = 2
                    st.info("Large graph detected — hiding low-frequency transitions automatically.")

                edges_df = edges_df[edges_df["count"] >= min_transition_count]
                edges_df = edges_df.nlargest(top_n_edges, "count")

                if edges_df.empty:
                    st.warning("No edges remain after filtering. Relax filters to view the graph.")
                else:
                    st.subheader("Edges")
                    st.dataframe(edges_df, use_container_width=True)
                    try:
                        mode_value = "force" if graph_mode == "Force" else "hierarchical"
                        graph_html = render_graph(
                            graph["nodes"],
                            edges_df.to_dict("records"),
                            mode=mode_value,
                            show_edge_labels=show_edge_labels,
                            show_node_counts=show_node_counts,
                        )
                        components.html(graph_html, height=650, scrolling=True)
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
    

                
