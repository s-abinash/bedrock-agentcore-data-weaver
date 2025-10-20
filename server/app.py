import os
import json
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
from langchain_aws import ChatBedrockConverse

try:
    from .data_analyzer_agentcore import analyze_data_with_agentcore
    from .s3_loader import load_multiple_from_s3
except ImportError:
    from server.data_analyzer_agentcore import analyze_data_with_agentcore
    from server.s3_loader import load_multiple_from_s3

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

SESSION_CACHE = {}

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
    runtime_session_id: str | None = None
    traceId: str | None = None
    baggage: str | None = None
    tracestate: str | None = None
    traceparent: str | None = None

def get_llm(provider: str | None = None):
    selected = (provider or os.environ.get("LLM_PROVIDER") or "aws").lower()

    if selected == "openai":
        return ChatOpenAI(
            model="gpt-4.1",
            temperature=0,
            api_key=os.environ.get("OPENAI_API_KEY")
        )

    model_id = os.environ.get("BEDROCK_MODEL_ID", "us.anthropic.claude-3-7-sonnet-20250219-v1:0")
    region = os.environ.get("AWS_REGION") or "us-west-2"
    return ChatBedrockConverse(
        model_id=model_id,
        region_name=region,
        temperature=0,
    )


def get_bedrock_llm():
    return get_llm("aws")


def _get_bedrock_agent_runtime_client():
    region = os.environ.get("AWS_REGION") or "us-west-2"

    logger.debug(
        "Creating Bedrock Agent Runtime client",
        extra={"region": region},
    )
    return boto3.client("bedrock-agentcore", region_name=region)


def _get_s3_bucket() -> str:
    bucket = os.environ.get("S3_BUCKET_NAME")
    if not bucket:
        raise HTTPException(
            status_code=500,
            detail="S3_BUCKET_NAME environment variable is not set",
        )
    return bucket


def _get_s3_client():
    region = os.environ.get("AWS_REGION") or "us-west-2"
    client_kwargs: Dict[str, str] = {"region_name": region}

    logger.debug("Creating boto3 S3 client", extra={"region": region})
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


def _get_chart_urls_from_s3(session_id: str, bucket: str) -> List[str]:
    try:
        s3_client = _get_s3_client()
        prefix = f"charts/{session_id}/"

        response = s3_client.list_objects_v2(Bucket=bucket, Prefix=prefix)

        if 'Contents' not in response:
            return []

        chart_urls = []
        for obj in response['Contents']:
            key = obj['Key']
            if key.lower().endswith(('.png', '.jpg', '.jpeg', '.svg', '.pdf')):
                presigned_url = s3_client.generate_presigned_url(
                    'get_object',
                    Params={'Bucket': bucket, 'Key': key},
                    ExpiresIn=3600
                )
                chart_urls.append(presigned_url)

        return chart_urls
    except (BotoCoreError, ClientError) as e:
        logger.warning(f"Failed to retrieve chart URLs from S3: {e}")
        return []

@app.get('/ping')
def ping():
    return {
        "status": "Healthy",
        "time_of_last_update": int(time.time())
    }


@app.post('/cleanup-session')
def cleanup_session(runtime_session_id: str):
    if runtime_session_id in SESSION_CACHE:
        session_id = SESSION_CACHE[runtime_session_id]
        del SESSION_CACHE[runtime_session_id]
        return {"message": f"Session {session_id} removed from cache for runtime session {runtime_session_id}"}
    return {"message": f"No session found for runtime session {runtime_session_id}"}


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

        llm = get_bedrock_llm()

        bucket = _get_s3_bucket()

        runtime_session_id = payload.runtime_session_id or request.headers.get("x-amzn-bedrock-agentcore-runtime-session-id")

        result = analyze_data_with_agentcore(df_dict, llm, prompt, bucket_name=bucket, runtime_session_id=runtime_session_id)

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


@app.post("/chat")
def chat(request: Request, payload: InvocationRequest):
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

        trace_headers = _extract_trace_headers(request.headers)
        trace_payload = _extract_trace_payload_overrides(payload)

        logger.info(
            "Chat request received",
            extra={
                "prompt_preview": prompt[:120],
                "dataframe_count": len(s3_urls),
                "trace_headers": trace_headers,
                "trace_payload": trace_payload,
            },
        )

        logger.debug("Preparing Bedrock Agent Runtime client")
        client = _get_bedrock_agent_runtime_client()

        agent_runtime_arn = os.environ.get("BEDROCK_AGENT_RUNTIME_ARN")
        if not agent_runtime_arn:
            raise HTTPException(
                status_code=500,
                detail="BEDROCK_AGENT_RUNTIME_ARN environment variable must be set.",
            )

        runtime_session_id = next(
            (
                value
                for key, value in trace_headers.items()
                if key.lower() == "x-amzn-bedrock-agentcore-runtime-session-id"
            ),
            None,
        )
        if not runtime_session_id:
            runtime_session_id = os.environ.get("BEDROCK_AGENT_RUNTIME_SESSION_ID") or uuid.uuid4().hex

        qualifier = os.environ.get("BEDROCK_AGENT_RUNTIME_QUALIFIER", "DEFAULT")

        runtime_payload = json.dumps(
            {
                "s3_urls": s3_urls,
                "prompt": prompt,
            }
        )

        logger.info(
            "Invoking Bedrock Agent Runtime",
            extra={
                "runtime_session_id": runtime_session_id,
                "dataframes": list(s3_urls.keys()),
                "agent_runtime_arn": agent_runtime_arn,
                "qualifier": qualifier,
            },
        )

        try:
            response = client.invoke_agent_runtime(
                agentRuntimeArn=agent_runtime_arn,
                runtimeSessionId=runtime_session_id,
                payload=runtime_payload,
                qualifier=qualifier,
            )
        except NoCredentialsError as exc:
            logger.exception("AWS credentials not found while invoking Bedrock Agent Runtime")
            raise HTTPException(
                status_code=500,
                detail="AWS credentials not found. Please configure AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY.",
            ) from exc
        except (BotoCoreError, ClientError) as exc:
            logger.exception("Failed to invoke Bedrock Agent Runtime")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to invoke Bedrock Agent Runtime: {exc}",
            ) from exc

        logger.debug("Bedrock Agent Runtime invocation returned, reading stream")
        response_stream = response.get("response")
        if response_stream is None:
            logger.error("Bedrock Agent Runtime response missing 'response' stream")
            raise HTTPException(
                status_code=500,
                detail="Bedrock Agent Runtime response malformed: missing response stream",
            )

        raw_body = response_stream.read()
        logger.debug(
            "Raw payload received from Bedrock runtime",
            extra={"runtime_session_id": runtime_session_id, "payload_length": len(raw_body) if hasattr(raw_body, "__len__") else None},
        )
        body_text = raw_body.decode("utf-8") if isinstance(raw_body, (bytes, bytearray)) else str(raw_body)

        try:
            response_data = json.loads(body_text)
        except json.JSONDecodeError:
            logger.warning("Failed to parse Bedrock Agent Runtime response as JSON; returning raw text")
            response_data = {"message": body_text}

        if isinstance(response_data, dict):
            intermediate_steps = (
                response_data.get("intermediate_steps")
                or response_data.get("intermediateSteps")
                or []
            )
            output = (
                response_data.get("output")
                or response_data.get("completion")
                or response_data
            )
            response_keys = list(response_data.keys())
        else:
            intermediate_steps = []
            output = response_data
            response_keys = []

        bucket = os.environ.get("S3_BUCKET_NAME")
        logger.info("Session ID: " + runtime_session_id)
        chart_urls: List[str] = []
        if bucket:
            logger.debug(
                "Scanning S3 for generated charts",
                extra={"bucket": bucket, "runtime_session_id": runtime_session_id},
            )
            chart_urls = _get_chart_urls_from_s3(runtime_session_id, bucket)
        logger.info(chart_urls)
        logger.info(
            "Chat invocation completed successfully",
            extra={
                "runtime_session_id": runtime_session_id,
                "dataframes_loaded": list(s3_urls.keys()),
                "response_keys": response_keys,
                "chart_count": len(chart_urls),
            },
        )

        return {
            "output": output,
            "intermediate_steps": intermediate_steps,
            "dataframes_loaded": list(s3_urls.keys()),
            "charts": chart_urls,
            "trace": {
                "headers": trace_headers,
                "payload": trace_payload,
                "runtime_session_id": runtime_session_id,
            },
        }

    except HTTPException:
        logger.exception("HTTPException raised while handling chat request")
        raise
    except Exception as exc:
        logger.exception("Unhandled exception during chat invocation")
        raise HTTPException(
            status_code=500,
            detail={
                "error": str(exc),
                "traceback": traceback.format_exc(),
            },
        ) from exc

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=8080, access_log=False)
