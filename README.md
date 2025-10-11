# Pandas Agent Core

A standalone pandas data analysis agent powered by LangChain and LangGraph. This agent can analyze pandas DataFrames using natural language queries and provide insights, visualizations, and analysis.

## Features

- Natural language data analysis with pandas
- Support for multiple DataFrames
- Automatic chart generation and visualization
- Extensible tool system
- Built on LangChain and LangGraph

## Installation

This project uses [uv](https://github.com/astral-sh/uv) for fast, reliable package management.

### Install uv (if not already installed)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Install dependencies

```bash
uv sync
```

This will create a virtual environment and install all required dependencies.

## Configuration

Create a `.env` file in the project root with your AWS credentials:

```bash
cp .env.example .env
```

Edit `.env` with your settings:

```env
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
S3_BUCKET_NAME=data-agent-bedrock-ac
```

The application automatically loads these environment variables on startup.

## Usage

### Basic Example

```python
import pandas as pd
from langchain_openai import ChatOpenAI
from server.data_analyzer import analyze_data

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

df = pd.DataFrame({
    'Product': ['Laptop', 'Mouse', 'Keyboard'],
    'Price': [999.99, 24.99, 79.99],
    'Sales': [150, 320, 210]
})

dataframes = {'sales_data': df}

prompt = "What is the total revenue for each product?"

result = analyze_data(dataframes, llm, prompt)
print(result['output'])
```

### Run the example

```bash
uv run python example.py
```

### Run the API server

```bash
uv run python -m server.app
```

### Using with Anthropic Claude

```python
from langchain_anthropic import ChatAnthropic

llm = ChatAnthropic(
    model="claude-3-5-sonnet-20241022",
    temperature=0
)

result = analyze_data(dataframes, llm, prompt)
```

## AWS Bedrock AgentCore Deployment

This agent is designed to deploy as an **Amazon Bedrock AgentCore** container.

### Build and Deploy

1. Build the Docker image for ARM64:

```bash
docker build --platform linux/arm64 -t pandas-agent-core .
```

2. Tag and push to Amazon ECR:

```bash
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <account-id>.dkr.ecr.us-east-1.amazonaws.com
docker tag pandas-agent-core:latest <account-id>.dkr.ecr.us-east-1.amazonaws.com/pandas-agent-core:latest
docker push <account-id>.dkr.ecr.us-east-1.amazonaws.com/pandas-agent-core:latest
```

3. Deploy to Bedrock AgentCore using the AWS Console or CLI

### API Endpoints

The container exposes the following endpoints required by Bedrock AgentCore:

- `POST /invocations` - Main agent invocation endpoint
- `GET /ping` - Health check endpoint

### Request Format

Send a POST request to `/invocations` with S3 URLs:

```json
{
  "s3_urls": {
    "sales_data": "s3://my-bucket/data/sales.csv",
    "inventory": "s3://my-bucket/data/inventory.xlsx"
  },
  "prompt": "What is the total revenue by category?"
}
```

Region is configured via environment variables (`.env` file).

**Supported File Formats:**
- CSV (`.csv`)
- Excel (`.xlsx`, `.xls`) - Multiple sheets supported, creates separate DataFrames
- Parquet (`.parquet`)
- JSON (`.json`)

### Response Format

```json
{
  "output": "Analysis results...",
  "intermediate_steps": [],
  "dataframes_loaded": ["sales_data", "inventory_Sheet1", "inventory_Sheet2"]
}
```

### Local Testing

Test the container locally:

```bash
docker run -p 8080:8080 \
  -e AWS_REGION=us-east-1 \
  -e AWS_ACCESS_KEY_ID=your-key \
  -e AWS_SECRET_ACCESS_KEY=your-secret \
  -e S3_BUCKET_NAME=data-agent-bedrock-ac \
  pandas-agent-core
```

Test the endpoint:

```bash
curl -X POST http://localhost:8080/invocations \
  -H "Content-Type: application/json" \
  -d '{
    "s3_urls": {
      "sales": "s3://my-bucket/sales.csv"
    },
    "prompt": "Show summary statistics"
  }'
```

## S3 Data Loading

The agent automatically loads data from S3 URLs and converts them to pandas DataFrames:

### Single File
```json
{
  "s3_urls": {
    "my_data": "s3://bucket/file.csv"
  }
}
```
Creates: `{"my_data": DataFrame}`

### Excel with Multiple Sheets
```json
{
  "s3_urls": {
    "financials": "s3://bucket/report.xlsx"
  }
}
```
If the Excel file has sheets "Q1", "Q2", "Q3", creates:
`{"financials_Q1": DataFrame, "financials_Q2": DataFrame, "financials_Q3": DataFrame}`

### Multiple Files
```json
{
  "s3_urls": {
    "sales": "s3://bucket/sales.parquet",
    "inventory": "s3://bucket/inventory.json"
  }
}
```
Creates: `{"sales": DataFrame, "inventory": DataFrame}`

## Project Structure

```
agent-core/
├── server/
│   ├── __init__.py
│   ├── app.py
│   ├── data_analyzer.py
│   ├── s3_loader.py
│   ├── agents/
│   │   └── pandas_agent.py
│   └── tools/
│       └── upload_image.py
├── ui/
│   └── ...
├── example.py
├── test_api.py
├── deploy.sh
├── Dockerfile
├── .dockerignore
├── .env.example
├── pyproject.toml
└── README.md
```

## API Reference

### analyze_data(dataframes, llm, prompt)

Main function to analyze pandas DataFrames using natural language.

**Parameters:**
- `dataframes` (dict): Dictionary of DataFrames with names as keys
- `llm` (LanguageModelLike): LangChain LLM instance
- `prompt` (str): Natural language query or analysis request

**Returns:**
- dict: Contains 'output' with analysis results and 'intermediate_steps'

## Dependencies

Core dependencies include:
- langchain
- langchain-experimental
- langchain-core
- langgraph
- pandas
- numpy
- matplotlib
- seaborn
- scikit-learn

## Development

To add new dependencies:

```bash
uv add package-name
```

To update dependencies:

```bash
uv sync --upgrade
```

## License

This project is standalone code for hackathon use.
