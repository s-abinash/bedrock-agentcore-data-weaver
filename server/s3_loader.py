import boto3
import pandas as pd
from io import BytesIO
from typing import Dict
import os
from urllib.parse import urlparse

def parse_s3_url(s3_url: str) -> tuple:
    parsed = urlparse(s3_url)
    bucket = parsed.netloc
    key = parsed.path.lstrip('/')
    return bucket, key

def get_file_extension(key: str) -> str:
    return key.split('.')[-1].lower()

def load_from_s3(s3_url: str, region_name: str = None) -> Dict[str, pd.DataFrame]:
    if region_name is None:
        region_name = os.environ.get("AWS_REGION") or "us-west-2"

    s3_client = boto3.client('s3', region_name=region_name)

    bucket, key = parse_s3_url(s3_url)

    response = s3_client.get_object(Bucket=bucket, Key=key)
    file_buffer = BytesIO(response['Body'].read())

    file_ext = get_file_extension(key)

    dataframes = {}

    if file_ext == 'csv':
        df = pd.read_csv(file_buffer)
        dataframes['data'] = df

    elif file_ext in ['xlsx', 'xls']:
        excel_file = pd.ExcelFile(file_buffer)
        for sheet_name in excel_file.sheet_names:
            dataframes[sheet_name] = pd.read_excel(excel_file, sheet_name=sheet_name)

    elif file_ext == 'parquet':
        df = pd.read_parquet(file_buffer)
        dataframes['data'] = df

    elif file_ext == 'json':
        df = pd.read_json(file_buffer)
        dataframes['data'] = df

    else:
        raise ValueError(f"Unsupported file format: {file_ext}")

    return dataframes

def load_multiple_from_s3(s3_urls: Dict[str, str], region_name: str = None) -> Dict[str, pd.DataFrame]:
    all_dataframes = {}

    for name, s3_url in s3_urls.items():
        dfs = load_from_s3(s3_url, region_name)

        if len(dfs) == 1:
            all_dataframes[name] = list(dfs.values())[0]
        else:
            for sheet_name, df in dfs.items():
                all_dataframes[f"{name}_{sheet_name}"] = df

    return all_dataframes
