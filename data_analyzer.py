from datetime import datetime

from langchain.agents import AgentType

from agents.pandas_agent import create_pandas_dataframe_agent
from tools.upload_image import move_image_to_static_server

AST_PERSISTENCE_INSTRUCTION = """
CRITICAL EXECUTION CONSTRAINT: This is a stateless Python environment where NOTHING persists between code executions. Every single code block is completely isolated.

MANDATORY REQUIREMENTS for EVERY code execution:
- Import ALL required libraries at the start of EACH code block
- Define ALL variables, functions, and classes within the SAME code block where they're used
- NEVER reference variables from previous code blocks
- Treat each code execution as if it's the first time running code

VIOLATION CONSEQUENCE: Any attempt to use undefined variables will result in NameError and complete failure.
"""
today = datetime.today()

AGENT_PREFIX = """
You are working with {num_dfs} pandas dataframes in Python named with different keys/names and consider each key as the name of the dataframe.

Available dataframes: {df_names}

CRITICAL - Response Format:
During analysis, you MUST follow this exact format for every response:

Thought: [your reasoning about what to do next]
Action: [the action to take - must be one of the available tools]
Action Input: [the input to the action]
Observation: [this will be filled automatically]

CRITICAL ERROR HANDLING:
- If you encounter AttributeError with DatetimeIndex and .dt, IMMEDIATELY switch approach
- For DatetimeIndex: use .year directly (no .dt needed)
- For Series with datetime: use .dt.year
- If an approach fails 2+ times, try a completely different method
- NEVER give up and provide template responses - always solve with actual data
- If stuck, break the problem into smaller debugging steps

PANDAS DTYPE HANDLING (CRITICAL):
- Always convert data types explicitly before operations
- Use .astype(float) for numeric columns before arithmetic
- Use pd.to_numeric(series, errors='coerce') for mixed types
- Check dtypes with .dtypes before operations
- Handle NaN values explicitly with fillna() or dropna()
- DatetimeIndex.year (NOT .dt.year)
- Series.dt.year (when Series has datetime dtype)
- Always check type before using .dt accessor
- If uncertain, convert to Series first: pd.Series(index_or_column)

Never deviate from this format during analysis steps. Always include Action: and Action Input: after every Thought.

When you have completed your analysis and are ready to provide the final answer:
1. Write ONLY: "Final Answer:"
2. Then provide your complete analysis in markdown format WITHOUT ANY TOOL CALLS.

Your final output should be comprehensive and follow the requested output format.
""" + f""" <Environment_Information>
        - Current year is {today.year}
        - Current month is {today.strftime('%b')}
        - Current date is {today.strftime('%Y-%m-%d')}
        </Environment_Information>
        """ + """
Please refer the provided variables first and then proceed extracting values. 
You should use the tools below to answer the question posed of you:
"""


def _to_snake_case(text):
    """Convert text to snake_case format."""
    return text.lower().replace(' ', '_')


def analyze_data(dataframes, llm, prompt):
    # Convert dataframe keys to snake_case
    snake_case_dataframes = {_to_snake_case(key): value for key, value in dataframes.items()}
    
    agent = create_pandas_dataframe_agent(
        llm,
        snake_case_dataframes,
        verbose=True,
        agent_type=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
        max_iterations=100,
        allow_dangerous_code=True,
        include_df_in_prompt=True,
        extra_tools=[move_image_to_static_server],
        agent_executor_kwargs={
            "handle_parsing_errors": True,
            "return_only": False
        },
        return_intermediate_steps=True,
        engine="pandas",
        python_agent="python_repl",
        prefix=AGENT_PREFIX
    )

    return agent.invoke(prompt)
