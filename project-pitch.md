## Project Name

DataWeaver

## Elevator Pitch

A Bedrock-native agent for conversational data analysis of S3 files, powered by LangGraph and Pandas.

## About the Project

### What inspired you?

The project was inspired by the need to simplify data analysis for users who are not proficient in Python or SQL. Our goal was to build a reusable and scalable agent for Amazon Bedrock that could accept natural language queries and perform complex data analysis on files stored in Amazon S3. We wanted to create a serverless, intelligent tool that could be easily integrated into various data workflows.

### What you learned

This project was a deep dive into building production-grade agents on AWS. Key technical learnings include:
- **Bedrock AgentCore Services:** We learned how to build and host an agent in Amazon Bedrock AgentCore Runtime, correctly implementing the `/ping` and `/invocations` endpoints and how to leverage observability and built in tools.
- **Bedrock AgentCore CodeInterpreter Tool:** We utilized built in code interperter tools that come in handy for all the agent data analysis tool calling
- **Stateful Agents with LangGraph:** We moved beyond simple chains and used LangGraph to construct a cyclical, stateful agent. This allows the agent to iteratively generate and execute Python code, reflect on the output, and self-correct if an error occurs.
- **End-to-End Observability:** We successfully integrated the AWS Distro for OpenTelemetry (ADOT) to achieve full observability. We learned to configure auto-instrumentation to trace requests from the Bedrock runtime through our FastAPI application and its interactions with other AWS services like S3.

### How you built your project

The project is a containerized web service with a Python backend and a Vue.js frontend.

- **Backend:** The core of the project is a Python LangGraph agent built with **FastAPI**. It exposes the API endpoints required by the Bedrock AgentCore runtime.
- **Agent Logic:** We used **LangChain** and **LangGraph** to define the agent's reasoning process. The agent is equipped with tools that allow it to:
    1.  Generate and execute Python (Pandas) code to analyze data.
    2.  Create visualizations using `matplotlib`.
    3.  Upload any generated charts to an S3 bucket and return the URL.
- **Data Handling:** The agent uses **boto3** to download and load data from S3 URIs passed in the invocation request. It supports CSV, Excel (including multiple sheets), Parquet, and JSON formats.
- **Deployment:** The entire application is packaged into a **Docker** image, ready to be pushed to Amazon ECR and deployed as a private agent in Amazon Bedrock AgentCore and in ECS as a server.
- **Frontend:** A lightweight **Vue.js** application provides a simple UI to interact with the agent for demonstration purposes deployed in Amplify

### Challenges you faced

- **Code Generation Reliability:** Ensuring the LLM consistently generated correct and safe Pandas code was a primary challenge. This required careful prompt engineering and defining a strict tool interface for the code execution environment.
- **Handling Diverse Data Structures:** Building a robust data loader that could handle various file formats and the nuances of multi-sheet Excel files required significant logic. The agent needed to correctly map a single S3 URI for an Excel file to multiple, uniquely named dataframes.
- **Tool Calling:** Instruct the agent to properly utilize tools like executeCommand, executeCode ets., based on needs and return relevant answer. 
- **Trace Context Propagation:** Configuring OpenTelemetry to correctly propagate trace context from the Bedrock runtime (via headers like `X-Amzn-Trace-Id`) through the FastAPI application was complex. It required specific configurations in the ADOT collector and ensuring the instrumentation was correctly capturing and forwarding trace IDs.

## Build With

Languages: Python, Vue.js
Frameworks & Libraries: FastAPI, LangChain, LangGraph, Pandas, Matplotlib
Platforms: Docker
Cloud Services: Amazon Bedrock AgentCore, ECS, Amazon S3, Amazon ECR, CloudWatch
APIs: Boto3 (AWS SDK)