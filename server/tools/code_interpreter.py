import json
import os
from typing import Dict, Any, Optional
from langchain_core.tools import tool
from bedrock_agentcore.tools.code_interpreter_client import CodeInterpreter


class CodeInterpreterManager:
    def __init__(
        self,
        region: Optional[str] = None,
        session_timeout_seconds: int = 1200,
        tool_id: Optional[str] = None
    ):
        self.region = region or os.environ.get("AWS_REGION", "us-west-2")
        self.session_timeout_seconds = session_timeout_seconds
        self.tool_id = tool_id or os.environ.get("CODE_INTERPRETER_TOOL_ID")
        self.code_client = None

    def start_session(self):
        if not self.code_client:
            if self.tool_id:
                self.code_client = CodeInterpreter(self.region, code_interpreter_id=self.tool_id)
            else:
                self.code_client = CodeInterpreter(self.region)
            self.code_client.start(session_timeout_seconds=self.session_timeout_seconds)

    def stop_session(self):
        if self.code_client:
            self.code_client.stop()
            self.code_client = None

    def invoke_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        if not self.code_client:
            raise RuntimeError("Code interpreter session not started")

        response = self.code_client.invoke(tool_name, arguments)
        for event in response["stream"]:
            return json.dumps(event["result"])

    def write_files(self, files_to_create: list) -> str:
        return self.invoke_tool("writeFiles", {"content": files_to_create})

    def list_files(self, path: str = "") -> str:
        return self.invoke_tool("listFiles", {"path": path})


code_interpreter_manager = CodeInterpreterManager()


@tool
def execute_python(code: str, description: str = "") -> str:
    """Execute Python code in the Amazon Bedrock AgentCore code interpreter sandbox.

    This tool runs Python code in an isolated sandbox environment that maintains state
    between executions. Data files have been pre-loaded into the sandbox and can be
    accessed directly by filename.

    Args:
        code: The Python code to execute
        description: Optional description of what the code does

    Returns:
        str: JSON formatted result containing the execution output
    """
    if description:
        code = f"# {description}\n{code}"

    if not code_interpreter_manager.code_client:
        raise RuntimeError("Code interpreter session not started. Call start_session() first.")

    response = code_interpreter_manager.code_client.invoke("executeCode", {
        "code": code,
        "language": "python",
        "clearContext": False
    })

    for event in response["stream"]:
        return json.dumps(event["result"])
