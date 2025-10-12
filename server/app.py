import os
import time
import uuid
import traceback
import logging
from typing import Dict, List

import boto3
from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, UploadFile, File, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from langchain_openai import ChatOpenAI

from .data_analyzer import analyze_data
from .s3_loader import load_multiple_from_s3

load_dotenv()

DEFAULT_OTEL_SERVICE_NAME = "pandas-agent-core"
if not os.environ.get("OTEL_SERVICE_NAME"):
    os.environ["OTEL_SERVICE_NAME"] = DEFAULT_OTEL_SERVICE_NAME

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
)
logger = logging.getLogger("pandas-agent-core")
uvicorn_logger = logging.getLogger("uvicorn.error")

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class InvocationRequest(BaseModel):
    s3_urls: Dict[str, str]
    prompt: str
    traceId: str | None = None
    baggage: str | None = None
    tracestate: str | None = None
    traceparent: str | None = None

def get_llm():
    return ChatOpenAI(
        model="gpt-4.1",
        temperature=0,
        api_key=os.environ.get("OPENAI_API_KEY")
    )


def _get_s3_bucket() -> str:
    bucket = os.environ.get("S3_BUCKET_NAME")
    if not bucket:
        raise HTTPException(
            status_code=500,
            detail="S3_BUCKET_NAME environment variable is not set",
        )
    return bucket


def _get_s3_client():
    region = os.environ.get("AWS_REGION", "us-east-1")
    client_kwargs: Dict[str, str] = {"region_name": region}

    access_key = os.environ.get("AWS_ACCESS_KEY_ID")
    secret_key = os.environ.get("AWS_SECRET_ACCESS_KEY")
    session_token = os.environ.get("AWS_SESSION_TOKEN")

    if access_key and secret_key:
        client_kwargs["aws_access_key_id"] = access_key
        client_kwargs["aws_secret_access_key"] = secret_key
        if session_token:
            client_kwargs["aws_session_token"] = session_token

    logger.debug("Creating boto3 S3 client", extra={"region": region, "has_explicit_creds": bool(access_key and secret_key)})
    return boto3.client("s3", **client_kwargs)


TRACE_HEADER_KEYS = {
    "x-amzn-trace-id",
    "traceparent",
    "tracestate",
    "baggage",
    "x-amzn-bedrock-agentcore-runtime-session-id",
    "mcp-session-id",
}


def _extract_trace_headers(headers: Dict[str, str]) -> Dict[str, str]:
    extracted = {}
    for key, value in headers.items():
        key_lower = key.lower()
        if key_lower in TRACE_HEADER_KEYS:
            extracted[key] = value
    return extracted


def _extract_trace_payload_overrides(payload: InvocationRequest) -> Dict[str, str]:
    trace_payload = {}
    if payload.traceId:
        trace_payload["traceId"] = payload.traceId
    if payload.baggage:
        trace_payload["baggage"] = payload.baggage
    if payload.tracestate:
        trace_payload["tracestate"] = payload.tracestate
    if payload.traceparent:
        trace_payload["traceparent"] = payload.traceparent
    return trace_payload

@app.get('/ping')
def ping():
    return {
        "status": "Healthy",
        "time_of_last_update": int(time.time())
    }


@app.post("/upload")
async def upload_files(
        request: Request,
        files: List[UploadFile] = File(...),
):
    try:
        if not files:
            raise HTTPException(
                status_code=400,
                detail="No files provided. Expected multipart form field 'files'."
            )

        normalized_files = files if isinstance(files, list) else [files]

        logger.info(
            "Received upload request",
            extra={
                "file_count": len(normalized_files),
                "client_host": request.client.host if request.client else None,
                "client_port": request.client.port if request.client else None,
                "user_agent": request.headers.get("user-agent", ""),
            },
        )

        bucket = _get_s3_bucket()
        s3_client = _get_s3_client()
        uploaded_files: Dict[str, str] = {}

        for index, upload in enumerate(normalized_files):
            base_name, extension = os.path.splitext(os.path.basename(upload.filename))
            sanitized_name = base_name or f"file_{index}"
            unique_key = f"{sanitized_name}_{uuid.uuid4().hex}{extension}"

            try:
                upload.file.seek(0)
                s3_client.upload_fileobj(upload.file, bucket, unique_key)
            except NoCredentialsError as exc:
                logger.exception(
                    "AWS credentials not found while uploading file",
                    extra={
                        "filename": upload.filename,
                        "bucket": bucket,
                        "key": unique_key,
                    },
                )
                raise HTTPException(
                    status_code=500,
                    detail="AWS credentials not found. Please configure AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY.",
                ) from exc
            except (BotoCoreError, ClientError) as exc:
                logger.exception(
                    "Failed to upload file to S3",
                    extra={
                        "filename": upload.filename,
                        "bucket": bucket,
                        "key": unique_key,
                    },
                )
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to upload {upload.filename}: {str(exc)}"
                ) from exc

            uploaded_files[sanitized_name] = f"s3://{bucket}/{unique_key}"

        logger.info(
            "Successfully uploaded files to S3",
            extra={"uploaded_files": uploaded_files, "bucket": bucket},
        )

        return {"s3_urls": uploaded_files}

    except HTTPException:
        logger.exception("HTTPException raised while handling upload request")
        raise
    except Exception as exc:
        logger.exception("Unhandled exception during upload")
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error while uploading files: {exc}",
        ) from exc


@app.post('/invocations')
def invocations(request: Request, payload: InvocationRequest):
    try:
        s3_urls = payload.s3_urls
        prompt = payload.prompt

        if not s3_urls:
            raise HTTPException(
                status_code=400,
                detail="No S3 URLs provided. Expected 's3_urls' field with dict of name->S3 URL"
            )

        if not prompt:
            raise HTTPException(
                status_code=400,
                detail="No prompt provided"
            )

        logger.info(
            "Invocation request received",
            extra={
                "prompt_preview": prompt[:120],
                "dataframe_count": len(s3_urls),
                "trace_headers": _extract_trace_headers(request.headers),
                "trace_payload": _extract_trace_payload_overrides(payload),
            },
        )

        df_dict = load_multiple_from_s3(s3_urls)

        if not df_dict:
            raise HTTPException(
                status_code=400,
                detail="No dataframes loaded from S3"
            )

        llm = get_llm()

        result = analyze_data(df_dict, llm, prompt)

        logger.info(
            "Invocation completed successfully",
            extra={
                "dataframes_loaded": list(df_dict.keys()),
                "intermediate_steps_count": len(result.get("intermediate_steps", [])),
            },
        )

        return {
            "output": result.get('output', ''),
            "intermediate_steps": result.get('intermediate_steps', []),
            "dataframes_loaded": list(df_dict.keys()),
            "trace": {
                "headers": _extract_trace_headers(request.headers),
                "payload": _extract_trace_payload_overrides(payload),
            }
        }

    except HTTPException:
        logger.exception("HTTPException raised while handling invocation request")
        raise
    except Exception as e:
        logger.exception("Unhandled exception during invocation")
        raise HTTPException(
            status_code=500,
            detail={
                "error": str(e),
                "traceback": traceback.format_exc()
            }
        )

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=8080)
