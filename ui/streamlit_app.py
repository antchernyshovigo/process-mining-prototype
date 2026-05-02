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


def render_graph(nodes, edges):
    net = Network(height="600px", width="100%", directed=True)
    net.force_atlas_2based()

    for node in nodes:
        size = max(20, 10 + int(node.get("count", 1)) * 2)
        label = f"{node['id']} ({node.get('count', 0)})"
        net.add_node(node["id"], label=label, size=size)

    for edge in edges:
        label = f"{edge['count']} | {edge['avg_duration_seconds']:.1f}s"
        width = max(1, min(8, int(edge['count'])))
        net.add_edge(edge['source'], edge['target'], label=label, width=width, arrows="to")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".html") as tmp_file:
        net.write_html(tmp_file.name)
        tmp_file_path = tmp_file.name

    with open(tmp_file_path, "r", encoding="utf-8") as f:
        return f.read()


# Sidebar для загрузки и настройки
with st.sidebar:
    st.header("Dataset Upload")
    
    uploaded_file = st.file_uploader("Choose CSV or Excel file", type=["csv", "xlsx"])
    
    if uploaded_file is not None:
        st.write(f"**File:** {uploaded_file.name}")
        
        st.subheader("Column Mapping")
        case_id_column = st.text_input("Case ID Column", value="case_id", key="case_id_input")
        event_name_column = st.text_input("Event Name Column", value="event_name", key="event_name_input")
        timestamp_column = st.text_input("Timestamp Column", value="timestamp", key="timestamp_input")
        
        if st.button("Upload Dataset", key="upload_btn"):
            with st.spinner("Uploading dataset..."):
                try:
                    files = {"file": (uploaded_file.name, uploaded_file, uploaded_file.type)}
                    data = {
                        "case_id_column": case_id_column,
                        "event_name_column": event_name_column,
                        "timestamp_column": timestamp_column,
                    }
                    
                    response = requests.post(
                        f"{API_BASE_URL}/datasets/upload",
                        files=files,
                        data=data
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        st.session_state.dataset_id = result["dataset_id"]
                        st.success(f"Dataset uploaded! ID: {result['dataset_id']}")
                        st.write(f"Rows (raw): {result['rows_count_raw']}")
                        st.write(f"Rows (processed): {result['rows_count_processed']}")
                    else:
                        st.error(f"Upload failed: {response.json()['detail']}")
                except Exception as e:
                    st.error(f"Error uploading file: {str(e)}")
    
    st.divider()
    st.subheader("Filters")
    min_transition_count = st.slider("Min Transition Count", 1, 10, 1)
    top_n_edges = st.slider("Top N Edges", 5, 50, 10)


# Основная часть
if st.session_state.dataset_id:
    dataset_id = st.session_state.dataset_id
    st.write(f"**Active Dataset:** {dataset_id}")
    
    # Вкладки для разных представлений
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["Summary", "Graph", "Variants", "Bottlenecks", "Health"])
    
    with tab1:
        st.header("Summary Metrics")
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
                st.error(f"Error: {response.json()['detail']}")
        except Exception as e:
            st.error(f"Error fetching summary: {str(e)}")
    
    with tab2:
        st.header("Process Graph")
        try:
            response = requests.get(f"{API_BASE_URL}/datasets/{dataset_id}/graph")
            if response.status_code == 200:
                graph = response.json()
                
                st.subheader("Nodes")
                nodes_df = pd.DataFrame(graph["nodes"])
                st.dataframe(nodes_df, use_container_width=True)
                
                st.subheader("Edges")
                edges_df = pd.DataFrame(graph["edges"])
                edges_df = edges_df[edges_df["count"] >= min_transition_count]
                edges_df = edges_df.nlargest(top_n_edges, "count")
                st.dataframe(edges_df, use_container_width=True)

                st.subheader("Graph Visualization")
                try:
                    graph_html = render_graph(graph["nodes"], edges_df.to_dict("records"))
                    components.html(graph_html, height=650, scrolling=True)
                except Exception as e:
                    st.error(f"Error rendering graph: {str(e)}")
            else:
                st.error(f"Error: {response.json()['detail']}")
        except Exception as e:
            st.error(f"Error fetching graph: {str(e)}")
    
    with tab3:
        st.header("Process Variants")
        try:
            response = requests.get(f"{API_BASE_URL}/datasets/{dataset_id}/variants")
            if response.status_code == 200:
                variants = response.json()
                variants_df = pd.DataFrame(variants)
                st.dataframe(variants_df, use_container_width=True)
            else:
                st.error(f"Error: {response.json()['detail']}")
        except Exception as e:
            st.error(f"Error fetching variants: {str(e)}")
    
    with tab4:
        st.header("Bottlenecks Analysis")
        try:
            response = requests.get(f"{API_BASE_URL}/datasets/{dataset_id}/bottlenecks")
            if response.status_code == 200:
                bottlenecks = response.json()
                
                st.subheader("Top by Avg Duration")
                avg_df = pd.DataFrame(bottlenecks["top_by_avg_duration"]).head(top_n_edges)
                st.dataframe(avg_df, use_container_width=True)
                
                st.subheader("Top by Median Duration")
                median_df = pd.DataFrame(bottlenecks["top_by_median_duration"]).head(top_n_edges)
                st.dataframe(median_df, use_container_width=True)
            else:
                st.error(f"Error: {response.json()['detail']}")
        except Exception as e:
            st.error(f"Error fetching bottlenecks: {str(e)}")
    
    with tab5:
        st.header("Health Check")
        try:
            response = requests.get(f"{API_BASE_URL}/health")
            if response.status_code == 200:
                st.success("✅ API is healthy")
                st.json(response.json())
            else:
                st.error("❌ API is unhealthy")
        except Exception as e:
            st.error(f"Error connecting to API: {str(e)}")

else:
    st.info("👈 Upload a dataset to get started")
