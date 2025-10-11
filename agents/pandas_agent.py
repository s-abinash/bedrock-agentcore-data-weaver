"""Agent for working with pandas objects."""

from typing import Any, Dict, List, Literal, Optional, Sequence, Union, cast
import warnings

from langchain.agents import (
    AgentType,
    create_openai_tools_agent,
    create_react_agent,
    create_tool_calling_agent,
)
from langchain.agents.agent import (
    AgentExecutor,
    BaseMultiActionAgent,
    BaseSingleActionAgent,
    RunnableAgent,
    RunnableMultiActionAgent,
)
from langchain.agents.mrkl.prompt import FORMAT_INSTRUCTIONS
from langchain.agents.openai_functions_agent.base import (
    OpenAIFunctionsAgent,
    create_openai_functions_agent,
)
from langchain_core.callbacks import BaseCallbackManager
from langchain_core.language_models import BaseLanguageModel, LanguageModelLike
from langchain_core.messages import SystemMessage
from langchain_core.prompts import (
    BasePromptTemplate,
    ChatPromptTemplate,
    PromptTemplate,
)
from langchain_core.tools import BaseTool
from langchain_core.utils.interactive_env import is_interactive_env

from langchain_experimental.tools.python.tool import PythonREPLTool, PythonAstREPLTool

from langgraph.graph import StateGraph
from langgraph.graph.state import CompiledStateGraph

# flake8: noqa

PREFIX = """
You are working with a pandas dataframe in Python. The name of the dataframe is `df`.
You should use the tools below to answer the question posed of you:"""

MULTI_DF_PREFIX = """
You are working with {num_dfs} pandas dataframes in Python named {df_names}. You 
should use the tools below to answer the question posed of you:"""

SUFFIX_NO_DF = """
Begin!
Question: {input}
{agent_scratchpad}"""

SUFFIX_WITH_DF = """
This is the result of `print(df.head())`:
{df_head}

Begin!
Question: {input}
{agent_scratchpad}"""

SUFFIX_WITH_MULTI_DF = """
This is the result of `print(df.head())` and `print(df.info) for each dataframe:
{dfs_head}

Begin!
Question: {input}
{agent_scratchpad}"""

PREFIX_FUNCTIONS = """
You are working with a pandas dataframe in Python. The name of the dataframe is `df`."""

MULTI_DF_PREFIX_FUNCTIONS = """
You are working with {num_dfs} pandas dataframes in Python named df1, df2, etc."""

FUNCTIONS_WITH_DF = """
This is the result of `print(df.head())`:
{df_head}"""

FUNCTIONS_WITH_MULTI_DF = """
This is the result of `print(df.head())` for each dataframe:
{dfs_head}"""


def _get_multi_prompt(
        dfs: List[Any] | Dict[str, Any],
        *,
        prefix: Optional[str] = None,
        suffix: Optional[str] = None,
        include_df_in_prompt: Optional[bool] = True,
        number_of_head_rows: int = 5,
) -> BasePromptTemplate:
    if suffix is not None:
        suffix_to_use = suffix
    elif include_df_in_prompt:
        suffix_to_use = SUFFIX_WITH_MULTI_DF
    else:
        suffix_to_use = SUFFIX_NO_DF
    prefix = prefix if prefix is not None else MULTI_DF_PREFIX

    template = "\n\n".join([prefix, "{tools}", FORMAT_INSTRUCTIONS, suffix_to_use])
    prompt = PromptTemplate.from_template(template)
    partial_prompt = prompt.partial()

    if "dfs_head" in partial_prompt.input_variables:
        if isinstance(dfs, dict):
            dfs_head_parts = []
            for key, df_item in dfs.items():
                dfs_head_parts.append(
                    f"{key}\nHead:\n{df_item.head(number_of_head_rows).to_markdown()}\nInfo:\n{df_item.info()}")
            dfs_head = "\n----\n".join(dfs_head_parts)
        else:
            dfs_head_parts = []
            for i, df_item in enumerate(dfs):
                dfs_head_parts.append(
                    f"{i}\nHead:\n{df_item.head(number_of_head_rows).to_markdown()}\nInfo:\n{df_item.info()}")
            dfs_head = "\n----\n".join(dfs_head_parts)
        partial_prompt = partial_prompt.partial(dfs_head=dfs_head)
    if "num_dfs" in partial_prompt.input_variables:
        if isinstance(dfs, dict):
            num_dfs = len(dfs.keys())
        else:
            num_dfs = len(dfs)
        partial_prompt = partial_prompt.partial(num_dfs=str(num_dfs))
    if "df_names" in partial_prompt.input_variables:
        if isinstance(dfs, dict):
            df_names = ", ".join([f"{key}" for key, value in dfs.items()])
        else:
            df_names = ", ".join([f"df{i + 1}" for i, df in enumerate(dfs)])
        partial_prompt = partial_prompt.partial(df_names=df_names)
    return partial_prompt


def _get_single_prompt(
        df: Any,
        *,
        prefix: Optional[str] = None,
        suffix: Optional[str] = None,
        include_df_in_prompt: Optional[bool] = True,
        number_of_head_rows: int = 5,
) -> BasePromptTemplate:
    if suffix is not None:
        suffix_to_use = suffix
    elif include_df_in_prompt:
        suffix_to_use = SUFFIX_WITH_DF
    else:
        suffix_to_use = SUFFIX_NO_DF
    prefix = prefix if prefix is not None else PREFIX

    template = "\n\n".join([prefix, "{tools}", FORMAT_INSTRUCTIONS, suffix_to_use])
    prompt = PromptTemplate.from_template(template)

    partial_prompt = prompt.partial()
    if "df_head" in partial_prompt.input_variables:
        df_head = str(df.head(number_of_head_rows).to_markdown())
        partial_prompt = partial_prompt.partial(df_head=df_head)
    return partial_prompt


def _get_prompt(df: Any, **kwargs: Any) -> BasePromptTemplate:
    if isinstance(df, list):
        return _get_multi_prompt(df, **kwargs)
    elif isinstance(df, dict):
        return _get_multi_prompt(df, **kwargs)
    else:
        return _get_single_prompt(df, **kwargs)


def _get_functions_single_prompt(
        df: Any,
        *,
        prefix: Optional[str] = None,
        suffix: str = "",
        include_df_in_prompt: Optional[bool] = True,
        number_of_head_rows: int = 5,
) -> ChatPromptTemplate:
    if include_df_in_prompt:
        df_head = str(df.head(number_of_head_rows).to_markdown())
        suffix = (suffix or FUNCTIONS_WITH_DF).format(df_head=df_head)
    prefix = prefix if prefix is not None else PREFIX_FUNCTIONS
    system_message = SystemMessage(content=prefix + suffix)
    prompt = OpenAIFunctionsAgent.create_prompt(system_message=system_message)
    return prompt


def _get_functions_multi_prompt(
        dfs: Any,
        *,
        prefix: str = "",
        suffix: str = "",
        include_df_in_prompt: Optional[bool] = True,
        number_of_head_rows: int = 5,
) -> ChatPromptTemplate:
    if include_df_in_prompt:
        dfs_head = "\n\n".join([d.head(number_of_head_rows).to_markdown() for d in dfs])
        suffix = (suffix or FUNCTIONS_WITH_MULTI_DF).format(dfs_head=dfs_head)
    prefix = (prefix or MULTI_DF_PREFIX_FUNCTIONS).format(num_dfs=str(len(dfs)))
    system_message = SystemMessage(content=prefix + suffix)
    prompt = OpenAIFunctionsAgent.create_prompt(system_message=system_message)
    return prompt


def _get_functions_prompt(df: Any, **kwargs: Any) -> ChatPromptTemplate:
    return (
        _get_functions_multi_prompt(df, **kwargs)
        if isinstance(df, list)
        else _get_functions_single_prompt(df, **kwargs)
    )


def create_pandas_dataframe_agent(
        llm: LanguageModelLike,
        df: Any,
        agent_type: Union[
            AgentType, Literal["openai-tools", "tool-calling"]
        ] = AgentType.ZERO_SHOT_REACT_DESCRIPTION,
        callback_manager: Optional[BaseCallbackManager] = None,
        prefix: Optional[str] = None,
        suffix: Optional[str] = None,
        input_variables: Optional[List[str]] = None,
        verbose: bool = False,
        return_intermediate_steps: bool = False,
        max_iterations: Optional[int] = 15,
        max_execution_time: Optional[float] = None,
        early_stopping_method: str = "generate",
        agent_executor_kwargs: Optional[Dict[str, Any]] = None,
        include_df_in_prompt: Optional[bool] = True,
        number_of_head_rows: int = 5,
        extra_tools: Sequence[BaseTool] = (),
        engine: Literal["pandas", "modin"] = "pandas",
        python_agent: Literal["python_ast_repl", "python_repl"] = "python_ast_repl",
        allow_dangerous_code: bool = False,
        **kwargs: Any,
) -> CompiledStateGraph:
    """Construct a Pandas agent from an LLM and dataframe(s).

    Security Notice:
        This agent relies on access to a python repl tool which can execute
        arbitrary code. This can be dangerous and requires a specially sandboxed
        environment to be safely used. Failure to run this code in a properly
        sandboxed environment can lead to arbitrary code execution vulnerabilities,
        which can lead to data breaches, data loss, or other security incidents.

        Do not use this code with untrusted inputs, with elevated permissions,
        or without consulting your security team about proper sandboxing!

        You must opt-in to use this functionality by setting allow_dangerous_code=True.

    Args:
        llm: Language model to use for the agent. If agent_type is "tool-calling" then
            llm is expected to support tool calling.
        df: Pandas dataframe or list of Pandas dataframes.
        agent_type: One of "tool-calling", "openai-tools", "openai-functions", or
            "zero-shot-react-description". Defaults to "zero-shot-react-description".
            "tool-calling" is recommended over the legacy "openai-tools" and
            "openai-functions" types.
        callback_manager: DEPRECATED. Pass "callbacks" key into 'agent_executor_kwargs'
            instead to pass constructor callbacks to AgentExecutor.
        prefix: Prompt prefix string.
        suffix: Prompt suffix string.
        input_variables: DEPRECATED. Input variables automatically inferred from
            constructed prompt.
        verbose: AgentExecutor verbosity.
        return_intermediate_steps: Passed to AgentExecutor init.
        max_iterations: Passed to AgentExecutor init.
        max_execution_time: Passed to AgentExecutor init.
        early_stopping_method: Passed to AgentExecutor init.
        agent_executor_kwargs: Arbitrary additional AgentExecutor args.
        include_df_in_prompt: Whether to include the first number_of_head_rows in the
            prompt. Must be None if suffix is not None.
        number_of_head_rows: Number of initial rows to include in prompt if
            include_df_in_prompt is True.
        extra_tools: Additional tools to give to agent on top of a PythonAstREPLTool.
        engine: One of "modin" or "pandas". Defaults to "pandas".
        allow_dangerous_code: bool, default False
            This agent relies on access to a python repl tool which can execute
            arbitrary code. This can be dangerous and requires a specially sandboxed
            environment to be safely used.
            Failure to properly sandbox this class can lead to arbitrary code execution
            vulnerabilities, which can lead to data breaches, data loss, or
            other security incidents.
            You must opt in to use this functionality by setting
            allow_dangerous_code=True.

        **kwargs: DEPRECATED. Not used, kept for backwards compatibility.

    Returns:
        An AgentExecutor with the specified agent_type agent and access to
        a PythonAstREPLTool with the DataFrame(s) and any user-provided extra_tools.

    Example:
        .. code-block:: python

            from langchain_openai import ChatOpenAI
            from langchain_experimental.agents import create_pandas_dataframe_agent
            import pandas as pd

            df = pd.read_csv("titanic.csv")
            llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0)
            agent_executor = create_pandas_dataframe_agent(
                llm,
                df,
                agent_type="tool-calling",
                verbose=True
            )

    """
    if not allow_dangerous_code:
        raise ValueError(
            "This agent relies on access to a python repl tool which can execute "
            "arbitrary code. This can be dangerous and requires a specially sandboxed "
            "environment to be safely used. Please read the security notice in the "
            "doc-string of this function. You must opt-in to use this functionality "
            "by setting allow_dangerous_code=True."
            "For general security guidelines, please see: "
            "https://python.langchain.com/docs/security/"
        )
    try:
        if engine == "modin":
            import modin.pandas as pd
        elif engine == "pandas":
            import pandas as pd
        else:
            raise ValueError(
                f"Unsupported engine {engine}. It must be one of 'modin' or 'pandas'."
            )
    except ImportError as e:
        raise ImportError(
            f"`{engine}` package not found, please install with `pip install {engine}`"
        ) from e

    if is_interactive_env():
        pd.set_option("display.max_columns", None)

    if engine == "modin":
        # Import standard pandas specifically for type-checking the input `df`
        # This is safe as the user is passing pandas DataFrames initially.
        import pandas as standard_pandas_for_conversion

        if isinstance(df, standard_pandas_for_conversion.DataFrame):
            df = pd.DataFrame(df)  # Convert to modin.pandas.DataFrame
        elif isinstance(df, list):
            converted_list = []
            for item in df:
                if isinstance(item, standard_pandas_for_conversion.DataFrame):
                    converted_list.append(pd.DataFrame(item))  # Convert to modin
                else:
                    converted_list.append(item)  # Keep as is (e.g., already modin, or non-df)
            df = converted_list
        elif isinstance(df, dict):
            converted_dict = {}
            for key, value in df.items():
                if isinstance(value, standard_pandas_for_conversion.DataFrame):
                    converted_dict[key] = pd.DataFrame(value)  # Convert to modin
                else:
                    converted_dict[key] = value  # Keep as is
            df = converted_dict

    for _df in (
            df.values() if isinstance(df, dict)
            else df if isinstance(df, list)
            else [df]
    ):
        if not isinstance(_df, pd.DataFrame):
            raise ValueError(f"Expected pandas DataFrame, got {type(_df)}")

    if input_variables:
        kwargs = kwargs or {}
        kwargs["input_variables"] = input_variables
    if kwargs:
        warnings.warn(
            f"Received additional kwargs {kwargs} which are no longer supported."
        )

    df_locals = {}
    try:
        import pandas as pd_tool
        import numpy as np_tool
        import matplotlib.pyplot as plt_tool
        import seaborn as sns_tool
        from datetime import datetime as datetime_tool
        import pandas as pd_tool
        import numpy as np_tool
        import matplotlib.pyplot as plt_tool
        import seaborn as sns_tool
        from datetime import datetime as datetime_class, timedelta, date
        import uuid
        import os
        import json
        import re
        import sklearn

        df_locals['pd'] = pd_tool
        df_locals['np'] = np_tool
        df_locals['plt'] = plt_tool
        df_locals['sns'] = sns_tool
        df_locals['datetime'] = datetime_class
        df_locals['timedelta'] = timedelta
        df_locals['date'] = date
        df_locals['uuid'] = uuid
        df_locals['os'] = os
        df_locals['warnings'] = warnings
        df_locals['json'] = json
        df_locals['re'] = re
        df_locals['sklearn'] = sklearn


    except ImportError:
        warnings.warn(
            "Could not import pandas, numpy, matplotlib.pyplot, or seaborn. "
            "These will not be available in the PythonAstREPLTool by default."
        )

    if isinstance(df, list):
        for i, dataframe in enumerate(df):
            df_locals[f"df{i + 1}"] = dataframe
    elif isinstance(df, dict):
        for key, dataframe in df.items():
            if not isinstance(dataframe, pd.DataFrame):
                raise ValueError(
                    f"Expected pandas DataFrame, got {type(dataframe)} for key {key}"
                )
            df_locals[key] = dataframe
    else:
        df_locals["df"] = df

    tools = []
    if python_agent == "python_ast_repl":

        tools = [PythonAstREPLTool(locals=df_locals, globals=df_locals)] + list(extra_tools)
    else:
        python_repl_tool = PythonREPLTool()
        for key, value in df_locals.items():
            python_repl_tool.python_repl.globals[key] = value

        tools = [python_repl_tool] + list(extra_tools or [])

    if agent_type == AgentType.ZERO_SHOT_REACT_DESCRIPTION:
        if include_df_in_prompt is not None and suffix is not None:
            raise ValueError(
                "If suffix is specified, include_df_in_prompt should not be."
            )
        prompt = _get_prompt(
            df,
            prefix=prefix,
            suffix=suffix,
            include_df_in_prompt=include_df_in_prompt,
            number_of_head_rows=number_of_head_rows,
        )
        agent: Union[BaseSingleActionAgent, BaseMultiActionAgent] = RunnableAgent(
            runnable=create_react_agent(llm, tools, prompt),  # type: ignore
            input_keys_arg=["input"],
            return_keys_arg=["output"],
        )
    elif agent_type in (AgentType.OPENAI_FUNCTIONS, "openai-tools", "tool-calling"):
        prompt = _get_functions_prompt(
            df,
            prefix=prefix,
            suffix=suffix,
            include_df_in_prompt=include_df_in_prompt,
            number_of_head_rows=number_of_head_rows,
        )
        if agent_type == AgentType.OPENAI_FUNCTIONS:
            runnable = create_openai_functions_agent(
                cast(BaseLanguageModel, llm), tools, prompt
            )
            agent = RunnableAgent(
                runnable=runnable,
                input_keys_arg=["input"],
                return_keys_arg=["output"],
            )
        else:
            if agent_type == "openai-tools":
                runnable = create_openai_tools_agent(
                    cast(BaseLanguageModel, llm), tools, prompt
                )
            else:
                runnable = create_tool_calling_agent(
                    cast(BaseLanguageModel, llm), tools, prompt
                )
            agent = RunnableMultiActionAgent(
                runnable=runnable,
                input_keys_arg=["input"],
                return_keys_arg=["output"],
            )
    else:
        raise ValueError(
            f"Agent type {agent_type} not supported at the moment. Must be one of "
            "'tool-calling', 'openai-tools', 'openai-functions', or "
            "'zero-shot-react-description'."
        )
    agent_executor = AgentExecutor(
        agent=agent,
        tools=tools,
        callback_manager=callback_manager,
        verbose=verbose,
        return_intermediate_steps=return_intermediate_steps,
        max_iterations=max_iterations,
        max_execution_time=max_execution_time,
        early_stopping_method=early_stopping_method,
        **(agent_executor_kwargs or {}),
    )

    from langgraph.graph import START, END
    
    graph = StateGraph(dict)
    # TODO: Add another node to validate the output and rerun the agent if needed.
    graph.add_node("agent", agent_executor)  # a one-node graph
    graph.add_edge(START, "agent")
    graph.add_edge("agent", END)

    compiled_graph = graph.compile()
    return compiled_graph
