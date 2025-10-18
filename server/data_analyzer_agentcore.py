from datetime import datetime
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
import pandas as pd
import io

from .tools.code_interpreter import execute_python, code_interpreter_manager


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
- The sandbox maintains state between executions, so you can refer to previous results
- Available data files can be loaded using pandas: pd.read_csv('filename.csv')
- All necessary libraries (pandas, numpy, matplotlib, seaborn, sklearn) are pre-installed
- To access a dataframe, you must load it from the CSV file in the sandbox

APPROACH:
- If asked about a programming concept, implement it in code to demonstrate
- If asked for calculations, compute them programmatically AND show the code
- If implementing algorithms, include test cases to prove correctness
- Document your validation process for transparency
- Always load data files at the beginning of your code execution

TOOL AVAILABLE:
- execute_python: Run Python code in the sandbox and see output

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

Be thorough, accurate, and always validate your answers when possible."""


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


def analyze_data_with_agentcore(dataframes, llm, prompt):
    files_to_create = _prepare_files_for_sandbox(dataframes)

    code_interpreter_manager.start_session()

    try:
        write_result = code_interpreter_manager.write_files(files_to_create)
        print(f"Files written to sandbox: {write_result}")

        list_result = code_interpreter_manager.list_files("")
        print(f"Files in sandbox: {list_result}")

        agent_prompt = ChatPromptTemplate.from_messages([
            ("system", AGENT_SYSTEM_PROMPT),
            ("user", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])

        tools = [execute_python]

        agent = create_tool_calling_agent(llm, tools, agent_prompt)
        agent_executor = AgentExecutor(
            agent=agent,
            tools=tools,
            verbose=True,
            max_iterations=100,
            handle_parsing_errors=True,
            return_intermediate_steps=True
        )

        dataframe_info = ", ".join([f"'{name}.csv'" for name in dataframes.keys()])
        enhanced_prompt = f"""Available data files in the sandbox: {dataframe_info}

Load these files using pandas before analyzing them.

User Query: {prompt}"""

        result = agent_executor.invoke({"input": enhanced_prompt})

        return result

    finally:
        code_interpreter_manager.stop_session()
