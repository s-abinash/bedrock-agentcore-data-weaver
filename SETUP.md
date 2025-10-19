## Prerequisites

- AWS account with Bedrock AgentCore access, an S3 bucket for uploads, and permission to invoke the Bedrock code interpreter.
- Docker (for container builds) and Node.js 18+.
- Python 3.11 (local execution) and [uv](https://github.com/astral-sh/uv) for Python dependency management.

## Backend (FastAPI)

```bash
# install Python deps
uv sync

# copy env template and fill values
cp .env.example .env

# run locally
uv run uvicorn server.app:app --host 0.0.0.0 --port 8080
```

### Required environment variables

| Variable | Description |
| --- | --- |
| `AWS_REGION` | Region for S3 and Bedrock (e.g. `us-west-2`) |
| `S3_BUCKET_NAME` | Bucket holding uploads and generated charts |
| `CODE_INTERPRETER_TOOL_ID` | Bedrock code interpreter ID used by the agent |
| `BEDROCK_AGENT_RUNTIME_ARN` | ARN of the Bedrock Agent Runtime (needed when running `/chat`) |
| `OPENAI_API_KEY` | OpenAI key used by the fallback model in `get_bedrock_llm` |

Optional: `BEDROCK_AGENT_RUNTIME_SESSION_ID`, `BEDROCK_AGENT_RUNTIME_QUALIFIER`, OTEL variables, etc.

## Frontend (Vue 3)

```bash
cd ui
npm install
npm run dev
```

Configure API base URL via `.env` (`VITE_API_BASE_URL`) or `window.__AGENT_CORE_API_BASE_URL`.

## AWS Resources Checklist

- **Bedrock Agent Runtime** deployed with the backend container.
- **Bedrock Code Interpreter** created with access to the runtime role (`CODE_INTERPRETER_TOOL_ID`).
- **S3 bucket** for uploads and chart artifacts (grant the runtime role read/write).
- **IAM task role** (if running in ECS) with `bedrock-agentcore:InvokeAgentRuntime` and required S3 permissions.

## Docker

```bash
docker build -t agentcore-insight-bridge .
# optional: docker run -p 8080:8080 agentcore-insight-bridge
```

Use this image for ECS and Bedrock Agent Runtime deployment, providing environment variables from `.env`.

## Sample Data Quickstart

The `sample/` directory includes datasets you can upload immediately:

- **Products.csv** – After uploading, ask:  
  `Which are the highest-priced and lowest-priced items overall (show Name, Brand, Category, Price)?`
- **Mall_Customers.csv** – For a more complex try:  
  `Please analyze the Mall_Customers.csv data and automatically discover natural customer groups based on Age, Annual Income, and Spending Score (you decide how many groups make sense). Show a simple scatter chart of Income vs. Spending with the groups clearly colored and their centers marked, give each group a friendly name with a one-line description, report how many customers fall into each group, and tell me which group CustomerID 59 belongs to.`

These prompts exercise both tabular summaries and chart generation so you can validate the deployment end-to-end.
