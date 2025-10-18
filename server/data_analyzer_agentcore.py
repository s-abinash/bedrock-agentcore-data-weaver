import json
import os
import boto3
from datetime import datetime
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
import pandas as pd
import io

from .tools.code_interpreter import create_code_interpreter_tools


today = datetime.today()

AGENT_SYSTEM_PROMPT = f"""You are a helpful AI assistant that validates all answers through code execution using the tools provided. DO NOT answer questions without using the tools.

VALIDATION PRINCIPLES:
1. When making claims about code, algorithms, or calculations - write code to verify them
2. Use execute_python to test mathematical calculations, algorithms, and logic
3. Create test scripts to validate your understanding before giving answers
4. Always show your work with actual code execution
5. If uncertain, explicitly state limitations and validate what you can

CODE INTERPRETER ENVIRONMENT:
- Data files have been pre-loaded into the sandbox environment
- The sandbox maintains state between executions - variables, imports, and installed packages persist
- Available data files can be loaded using pandas: pd.read_csv('filename.csv')
- Common libraries are available: pandas, numpy, matplotlib
- For visualizations, use ONLY matplotlib (import matplotlib.pyplot as plt)
- To access a dataframe, you must load it from the CSV file in the sandbox

IMPORTANT STATE MANAGEMENT:
- Once you load data into a variable, it stays in memory - DO NOT reload unnecessarily
- Once you install a package with executeCommand, it stays installed - DO NOT reinstall
- Variables from previous executions are available - you can reference them directly
- If you get an import error, install the package ONCE using executeCommand, then continue your analysis
- After installing a package, simply continue with your code - DO NOT start from scratch

CORRECT WORKFLOW EXAMPLE:
1. Load data: df = pd.read_csv('data.csv')
2. Analyze: df.describe(), df.info()
3. Visualize: import matplotlib.pyplot as plt; plt.figure(); plt.hist(df['column']); plt.savefig('chart.png')
4. If you need additional packages, install ONCE and continue
5. The variable 'df' is still available, no need to reload!

WRONG WORKFLOW (DO NOT DO THIS):
1. Load data: df = pd.read_csv('data.csv')
2. Try something that needs a package -> gets error
3. Install package: execute_command("pip install package")
4. START OVER: df = pd.read_csv('data.csv') again <- UNNECESSARY!
5. Re-import and analyze <- WASTES TIME!

APPROACH:
- If asked about a programming concept, implement it in code to demonstrate
- If asked for calculations, compute them programmatically AND show the code
- If implementing algorithms, include test cases to prove correctness
- Document your validation process for transparency
- Load data files ONCE at the beginning, then reuse the loaded dataframes

TOOLS AVAILABLE:
- execute_python: Run Python code in the sandbox and see output
- execute_command: Execute shell commands in the sandbox (for installing packages, uploading to S3, etc.)

SESSION RULES:
- Perform the requested analysis only once per user query.
- After you have validated the answer and prepared any requested artifacts, craft a final response and stop.
- Do NOT restart the workflow, reload data, or reinstall packages unless explicitly asked in a new user instruction.
- Always include a clear hand-off that the analysis is finished.
- Do NOT expose internal identifiers (session IDs, storage keys) or implementation details in your replies.

CHART GENERATION AND UPLOAD:
- When asked to create charts or visualizations, use ONLY matplotlib (DO NOT use seaborn or other libraries)
- Import as: import matplotlib.pyplot as plt
- Save charts with descriptive filenames (e.g., 'sales_trend.png', 'correlation_heatmap.png')
- Use plt.savefig('filename.png', bbox_inches='tight', dpi=150) to save charts
- After creating charts, upload them to S3 using: execute_command with aws s3 cp
- The S3 upload path (bucket and session_id) will be provided in the query
- Always use the provided session storage key when saving artifacts to S3; do NOT substitute the interpreter session id.
- Do not include explicit S3 URIs, file system paths, or upload commands in your final answer—reference charts descriptively instead.

RESPONSE FORMAT:
The execute_python tool returns a JSON response with:
- sessionId: The sandbox session ID
- id: Request ID
- isError: Boolean indicating if there was an error
- content: Array of content objects with type and text/data
- structuredContent: For code execution, includes stdout, stderr, exitCode, executionTime

For successful code execution, the output will be in content[0].text and also in structuredContent.stdout.
Check isError field to see if there was an error.

CRITICAL ERROR HANDLING:
- If you encounter AttributeError with DatetimeIndex and .dt, IMMEDIATELY switch approach
- For DatetimeIndex: use .year directly (no .dt needed)
- For Series with datetime: use .dt.year
- If an approach fails 2+ times, try a completely different method
- NEVER give up and provide template responses - always solve with actual data
- If stuck, break the problem into smaller debugging steps

PANDAS DTYPE HANDLING:
- Always convert data types explicitly before operations
- Use .astype(float) for numeric columns before arithmetic
- Use pd.to_numeric(series, errors='coerce') for mixed types
- Check dtypes with .dtypes before operations
- Handle NaN values explicitly with fillna() or dropna()

Environment Information:
- Current year is {today.year}
- Current month is {today.strftime('%b')}
- Current date is {today.strftime('%Y-%m-%d')}

RESPONSE STYLE:
- Present answers in clear Markdown with headings, bullet lists, and tables when appropriate.
- Summaries should remain concise and focused on actionable insights.
- Call out any generated charts by name or description only—omit storage details.
- Avoid templated sign-offs such as "Analysis complete."

Be thorough, accurate, and always validate your answers when possible. Respond in Markdown and end once the question is fully addressed."""


def _prepare_files_for_sandbox(dataframes: dict) -> list:
    files_to_create = []

    for name, df in dataframes.items():
        csv_buffer = io.StringIO()
        df.to_csv(csv_buffer, index=False)
        csv_content = csv_buffer.getvalue()

        files_to_create.append({
            "path": f"{name}.csv",
            "text": csv_content
        })

    return files_to_create


def analyze_data_with_agentcore(dataframes, llm, prompt, bucket_name=None, runtime_session_id=None):
    from server.app import SESSION_CACHE

    files_to_create = _prepare_files_for_sandbox(dataframes)

    region = os.environ.get("AWS_REGION") or "us-west-2"
    interpreter_id = os.environ.get("CODE_INTERPRETER_TOOL_ID")

    if not interpreter_id:
        raise ValueError("CODE_INTERPRETER_TOOL_ID environment variable must be set")

    dp_client = boto3.client("bedrock-agentcore", region_name=region)

    session_id = None
    is_new_session = False

    if runtime_session_id and runtime_session_id in SESSION_CACHE:
        session_id = SESSION_CACHE[runtime_session_id]
        print(f"Reusing existing session: {session_id} for runtime session: {runtime_session_id}")
    else:
        session_response = dp_client.start_code_interpreter_session(
            codeInterpreterIdentifier=interpreter_id,
            sessionTimeoutSeconds=1200
        )
        session_id = session_response["sessionId"]
        is_new_session = True
        if runtime_session_id:
            SESSION_CACHE[runtime_session_id] = session_id
        print(f"Started new session: {session_id} for runtime session: {runtime_session_id}")

    try:
        if is_new_session:
            response = dp_client.invoke_code_interpreter(
                codeInterpreterIdentifier=interpreter_id,
                sessionId=session_id,
                name="writeFiles",
                arguments={"content": files_to_create}
            )
            for event in response["stream"]:
                write_result = json.dumps(event["result"])
                print(f"Files written to sandbox: {write_result}")
                break

            response = dp_client.invoke_code_interpreter(
                codeInterpreterIdentifier=interpreter_id,
                sessionId=session_id,
                name="executeCommand",
                arguments={"command": "pip install boto3"}
            )
            for event in response["stream"]:
                install_result = json.dumps(event["result"])
                print(f"Boto3 installation result: {install_result}")
                break

            response = dp_client.invoke_code_interpreter(
                codeInterpreterIdentifier=interpreter_id,
                sessionId=session_id,
                name="listFiles",
                arguments={"path": ""}
            )
            for event in response["stream"]:
                list_result = json.dumps(event["result"])
                print(f"Files in sandbox: {list_result}")
                break
        else:
            print("Skipping file upload and package installation - reusing existing session")

        artifact_session_id = runtime_session_id or session_id
        print(
            f"Artifact storage key resolved: {artifact_session_id} "
            f"(runtime_session_id={runtime_session_id}, interpreter_session_id={session_id})"
        )

        if bucket_name is None:
            bucket_name = os.environ.get("S3_BUCKET_NAME", "")

        execute_python, execute_command = create_code_interpreter_tools(dp_client, interpreter_id, session_id)

        agent_prompt = ChatPromptTemplate.from_messages([
            ("system", AGENT_SYSTEM_PROMPT),
            ("user", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])

        tools = [execute_python, execute_command]

        agent = create_tool_calling_agent(llm, tools, agent_prompt)
        agent_executor = AgentExecutor(
            agent=agent,
            tools=tools,
            verbose=True,
            max_iterations=40,
            early_stopping_method="generate",
            handle_parsing_errors=True,
            return_intermediate_steps=True
        )

        dataframe_info = ", ".join([f"'{name}.csv'" for name in dataframes.keys()])

        s3_config = ""
        if bucket_name:
            s3_config = f"""
                Install any dependencies if required using pip.
                S3 Configuration (for chart uploads):
                - Bucket: {bucket_name}
                - Session Storage Key (use ONLY this for S3 paths): {artifact_session_id}
                - Upload path format: s3://{bucket_name}/charts/{artifact_session_id}/<filename>.png
                - Upload each chart only once; reuse existing files when rerunning cells.
                """

        storage_guidance = f"Session storage key for artifacts (internal use only, do not mention externally): {artifact_session_id}"

        enhanced_prompt = f"""Available data files in the sandbox: {dataframe_info}

        Load these files using pandas before analyzing them.
        {s3_config}
        {storage_guidance}
        User Query: {prompt}

        RESPONSE EXPECTATIONS:
        - Respond in well-structured Markdown (headings, bullet lists, tables as needed).
        - Highlight key insights succinctly; focus on actionable findings.
        - If charts were generated, reference them descriptively (e.g., "Customer distribution bar chart") without sharing S3 paths or IDs.
        - Do not include implementation details, storage keys, or closing phrases like "Analysis complete."
        """

        result = agent_executor.invoke({"input": enhanced_prompt})

        return result

    except Exception as e:
        if runtime_session_id and runtime_session_id in SESSION_CACHE:
            del SESSION_CACHE[runtime_session_id]
        raise
