import streamlit as st
import boto3
import os
import requests
import re
from dotenv import load_dotenv
import pandas as pd

load_dotenv()

st.set_page_config(
    page_title="AWS Data Agent",
    page_icon="https://a.b.cdn.console.awsstatic.com/a/v1/JH6LNPYTBZQF3PLGY3KXRE32RXTHCSMOCB2MLYGK23NUWCQXRFYQ/icon/289ffeb2a745ccf51ca89a297f47e382-e23370428c208f1105171354f38d8a21.svg",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
    <style>
    .stApp {
        background-color: #f8f9fa;
    }
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }
    h1 {
        color: #1e3a8a;
        font-weight: 600;
    }
    h2, h3 {
        color: #2563eb;
    }
    .stButton > button {
        background-color: #2563eb;
        color: white;
        border-radius: 6px;
        padding: 0.5rem 2rem;
        font-weight: 500;
        border: none;
        transition: background-color 0.3s;
    }
    .stButton > button:hover {
        background-color: #1d4ed8;
    }
    .stTextArea > div > div > textarea {
        border-color: #bfdbfe;
        border-radius: 6px;
    }
    .stTextArea > div > div > textarea:focus {
        border-color: #2563eb;
        box-shadow: 0 0 0 1px #2563eb;
    }
    .uploadedFile {
        background-color: #eff6ff;
        border: 1px solid #bfdbfe;
        border-radius: 6px;
        padding: 0.5rem 1rem;
    }
    .stExpander {
        background-color: white;
        border: 1px solid #e5e7eb;
        border-radius: 6px;
    }
    .stDataFrame {
        border: 1px solid #e5e7eb;
        border-radius: 6px;
    }
    .stAlert {
        border-radius: 6px;
    }
    .title-container {
        display: flex;
        align-items: center;
        gap: 1rem;
        margin-bottom: 1rem;
    }
    .title-container img {
        height: 48px;
        width: 48px;
    }
    .title-container h1 {
        margin: 0;
    }
    </style>
""", unsafe_allow_html=True)

def upload_to_s3(file, bucket_name):
    s3_client = boto3.client(
        's3',
        region_name=os.environ.get("AWS_REGION", "us-east-1"),
        aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY")
    )

    file_name = file.name
    s3_key = file_name

    s3_client.upload_fileobj(file, bucket_name, s3_key)

    s3_uri = f"s3://{bucket_name}/{s3_key}"
    return s3_uri

def parse_markdown_tables(text):
    table_pattern = r'\|(.+)\|[\r\n]+\|[-:\s|]+\|[\r\n]+((?:\|.+\|[\r\n]+)*)'

    parts = []
    last_end = 0

    for match in re.finditer(table_pattern, text):
        if match.start() > last_end:
            parts.append(('text', text[last_end:match.start()]))

        table_text = match.group(0)
        lines = [line.strip() for line in table_text.strip().split('\n')]

        headers = [cell.strip() for cell in lines[0].split('|')[1:-1]]

        rows = []
        for line in lines[2:]:
            if line.strip():
                cells = [cell.strip() for cell in line.split('|')[1:-1]]
                rows.append(cells)

        if rows:
            df = pd.DataFrame(rows, columns=headers)
            parts.append(('table', df))

        last_end = match.end()

    if last_end < len(text):
        parts.append(('text', text[last_end:]))

    return parts

st.markdown("""
    <div class="title-container">
        <img src="https://a.b.cdn.console.awsstatic.com/a/v1/JH6LNPYTBZQF3PLGY3KXRE32RXTHCSMOCB2MLYGK23NUWCQXRFYQ/icon/289ffeb2a745ccf51ca89a297f47e382-e23370428c208f1105171354f38d8a21.svg" alt="AWS">
        <h1>AWS Data Agent</h1>
    </div>
""", unsafe_allow_html=True)

if 'current_query' not in st.session_state:
    st.session_state.current_query = ""

if 's3_uris' not in st.session_state:
    st.session_state.s3_uris = {}

bucket_name = os.environ.get("S3_BUCKET_NAME", "data-agent-bedrock-ac")

uploaded_files = st.file_uploader(
    "Choose files to analyze",
    type=['csv', 'xlsx', 'xls', 'parquet', 'json'],
    accept_multiple_files=True,
    help="Upload up to 5 files (CSV, Excel, Parquet, or JSON)"
)

if uploaded_files:
    if len(uploaded_files) > 5:
        st.error("Maximum 5 files allowed. Please remove some files.")
    else:
        col1, col2 = st.columns([4, 1])

        with col1:
            st.write(f"{len(uploaded_files)} file(s) selected")

        with col2:
            if st.button("Upload to S3", type="primary", use_container_width=True):
                with st.spinner("Uploading files..."):
                    st.session_state.s3_uris = {}
                    upload_success = True

                    for file in uploaded_files:
                        try:
                            file.seek(0)
                            s3_uri = upload_to_s3(file, bucket_name)
                            file_key = file.name.rsplit('.', 1)[0]
                            st.session_state.s3_uris[file_key] = s3_uri
                        except Exception as e:
                            st.error(f"Failed to upload {file.name}: {str(e)}")
                            upload_success = False

                    if upload_success:
                        st.success(f"Successfully uploaded {len(uploaded_files)} file(s)")

if st.session_state.s3_uris:

    with st.expander("Uploaded Files", expanded=False):
        for key, uri in st.session_state.s3_uris.items():
            st.code(f"{key}: {uri}", language="text")

    st.markdown("---")

    query_text = st.text_area(
        "What would you like to analyze?",
        value=st.session_state.current_query,
        height=150,
        help="Describe the analysis you want to perform on the uploaded data"
    )

    st.session_state.current_query = query_text

    if st.button("Run Analysis", type="primary"):
        if query_text.strip():
            with st.spinner("Running deep analysis on uploaded data..."):
                try:
                    response = requests.post(
                        "http://localhost:8080/invocations",
                        json={
                            "s3_urls": st.session_state.s3_uris,
                            "prompt": query_text
                        },
                        timeout=300
                    )

                    if response.status_code == 200:
                        result = response.json()

                        st.markdown("---")
                        st.subheader("Results")

                        output = result.get('output', '')
                        parts = parse_markdown_tables(output)

                        if parts:
                            for part_type, content in parts:
                                if part_type == 'text' and content.strip():
                                    st.markdown(content)
                                elif part_type == 'table':
                                    st.dataframe(
                                        content,
                                        use_container_width=True,
                                        height=min(400, (len(content) + 1) * 35 + 3)
                                    )
                        else:
                            st.markdown(output)

                        with st.expander("Processing Details", expanded=False):
                            st.json(result.get('intermediate_steps', []))

                        dataframes_loaded = result.get('dataframes_loaded', [])
                        if dataframes_loaded:
                            st.caption(f"Dataframes analyzed: {', '.join(dataframes_loaded)}")

                    else:
                        st.error(f"Analysis failed with status code: {response.status_code}")
                        error_detail = response.json()
                        with st.expander("Error Details", expanded=True):
                            st.json(error_detail)

                except requests.exceptions.Timeout:
                    st.error("Analysis timed out. Please try with a simpler query or smaller dataset.")
                except Exception as e:
                    st.error(f"Analysis failed: {str(e)}")
        else:
            st.warning("Please enter an analysis query.")

else:
    st.info("Upload data files to begin analysis.")

st.markdown("---")
st.caption("Powered by OpenAI GPT-4 and LangChain")
