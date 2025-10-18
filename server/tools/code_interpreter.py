import json
from langchain_core.tools import tool


def create_code_interpreter_tools(dp_client, interpreter_id, session_id):
    """Create tools with dp_client, interpreter_id, and session_id in closure"""

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

        response = dp_client.invoke_code_interpreter(
            codeInterpreterIdentifier=interpreter_id,
            sessionId=session_id,
            name="executeCode",
            arguments={
                "code": code,
                "language": "python",
                "clearContext": False
            }
        )

        for event in response["stream"]:
            return json.dumps(event["result"])

    @tool
    def execute_command(command: str) -> str:
        """Execute shell commands in the Amazon Bedrock AgentCore code interpreter sandbox.

        This tool runs shell commands in the sandbox environment. Useful for operations like
        installing packages, managing files, or uploading files to S3.

        Args:
            command: The shell command to execute

        Returns:
            str: JSON formatted result containing the command execution output
        """
        response = dp_client.invoke_code_interpreter(
            codeInterpreterIdentifier=interpreter_id,
            sessionId=session_id,
            name="executeCommand",
            arguments={"command": command}
        )

        for event in response["stream"]:
            return json.dumps(event["result"])

    return execute_python, execute_command
