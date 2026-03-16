"""Built-in tools for agents — file system, math, shell."""

import ast
import logging
import operator
from pathlib import Path

from pulsar_ai.agent.tool import Tool, ToolRegistry

logger = logging.getLogger(__name__)


def _search_files(query: str, directory: str = ".") -> str:
    """Search for files matching a pattern in a directory.

    Args:
        query: Glob pattern or substring to match.
        directory: Root directory to search in.

    Returns:
        Newline-separated list of matching file paths.
    """
    root = Path(directory)
    if not root.exists():
        return f"Error: Directory '{directory}' does not exist."

    matches = []
    try:
        for path in root.rglob(f"*{query}*"):
            if path.is_file():
                matches.append(str(path.relative_to(root)))
                if len(matches) >= 50:
                    matches.append("... (truncated at 50 results)")
                    break
    except PermissionError:
        return "Error: Permission denied while searching."

    if not matches:
        return f"No files found matching '{query}' in {directory}"
    return "\n".join(matches)


def _read_file(path: str, max_lines: int = 200) -> str:
    """Read the contents of a file.

    Args:
        path: Path to the file to read.
        max_lines: Maximum number of lines to return.

    Returns:
        File contents as string.
    """
    file_path = Path(path)
    if not file_path.exists():
        return f"Error: File '{path}' does not exist."
    if not file_path.is_file():
        return f"Error: '{path}' is not a file."

    try:
        text = file_path.read_text(encoding="utf-8")
        lines = text.splitlines()
        if len(lines) > max_lines:
            return (
                "\n".join(lines[:max_lines]) + f"\n\n... ({len(lines) - max_lines} lines truncated)"
            )
        return text
    except UnicodeDecodeError:
        return f"Error: File '{path}' is not a text file."
    except PermissionError:
        return f"Error: Permission denied reading '{path}'."


def _list_directory(path: str = ".") -> str:
    """List contents of a directory.

    Args:
        path: Directory path to list.

    Returns:
        Formatted directory listing.
    """
    dir_path = Path(path)
    if not dir_path.exists():
        return f"Error: Directory '{path}' does not exist."
    if not dir_path.is_dir():
        return f"Error: '{path}' is not a directory."

    entries = []
    try:
        for entry in sorted(dir_path.iterdir()):
            prefix = "[DIR] " if entry.is_dir() else "      "
            entries.append(f"{prefix}{entry.name}")
    except PermissionError:
        return f"Error: Permission denied listing '{path}'."

    if not entries:
        return f"Directory '{path}' is empty."
    return "\n".join(entries)


_SAFE_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
    ast.FloorDiv: operator.floordiv,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def _safe_eval_node(node: ast.AST) -> float:
    """Recursively evaluate an AST node for safe math expressions.

    Args:
        node: AST node to evaluate.

    Returns:
        Numeric result.

    Raises:
        ValueError: If the node type is not supported.
    """
    if isinstance(node, ast.Expression):
        return _safe_eval_node(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _SAFE_OPS:
        left = _safe_eval_node(node.left)
        right = _safe_eval_node(node.right)
        return _SAFE_OPS[type(node.op)](left, right)
    if isinstance(node, ast.UnaryOp) and type(node.op) in _SAFE_OPS:
        return _SAFE_OPS[type(node.op)](_safe_eval_node(node.operand))
    raise ValueError(f"Unsupported expression: {ast.dump(node)}")


def _calculate(expression: str) -> str:
    """Evaluate a mathematical expression safely using AST parsing.

    Args:
        expression: Mathematical expression to evaluate.

    Returns:
        Result as string.
    """
    try:
        tree = ast.parse(expression.strip(), mode="eval")
        result = _safe_eval_node(tree)
        return str(result)
    except (SyntaxError, ValueError, ZeroDivisionError, TypeError) as e:
        return f"Error: {e}"


# Pre-built tool instances
search_files = Tool(
    name="search_files",
    description="Search for files matching a pattern in a directory tree",
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Pattern to search for"},
            "directory": {
                "type": "string",
                "description": "Root directory (default: current)",
                "default": ".",
            },
        },
        "required": ["query"],
    },
    func=_search_files,
)

read_file = Tool(
    name="read_file",
    description="Read the contents of a file",
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path to the file"},
            "max_lines": {
                "type": "integer",
                "description": "Max lines to return (default: 200)",
                "default": 200,
            },
        },
        "required": ["path"],
    },
    func=_read_file,
)

list_directory = Tool(
    name="list_directory",
    description="List contents of a directory",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Directory path (default: current)",
                "default": ".",
            },
        },
    },
    func=_list_directory,
)

calculate = Tool(
    name="calculate",
    description="Evaluate a mathematical expression",
    parameters={
        "type": "object",
        "properties": {
            "expression": {
                "type": "string",
                "description": "Mathematical expression to evaluate",
            },
        },
        "required": ["expression"],
    },
    func=_calculate,
)

# All built-in tools
ALL_BUILTIN_TOOLS = [search_files, read_file, list_directory, calculate]


def get_default_registry() -> ToolRegistry:
    """Create a ToolRegistry with all built-in tools.

    Returns:
        ToolRegistry with search_files, read_file, list_directory, calculate.
    """
    registry = ToolRegistry()
    for t in ALL_BUILTIN_TOOLS:
        registry.register(t)
    return registry
