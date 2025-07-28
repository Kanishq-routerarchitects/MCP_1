import os
import json
from datetime import datetime
from typing import List
from fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP("Tagged Demo Server")

# --- Self-Managed Tool Registry ---
# This list will hold all our tool objects, making discovery reliable.
TOOL_REGISTRY = []
def register(tool_func):
    """A decorator to add a tool to our registry after it's created."""
    TOOL_REGISTRY.append(tool_func)
    return tool_func

# --- Tool Definitions with Tags ---
# Decorator order: @mcp.tool runs first, then @register adds the result.

@register
@mcp.tool(tags=['math', 'basic'])
def add(a: int, b: int) -> int:
    """Adds two integers together."""
    print(f"Executing 'add' tool with a={a}, b={b}")
    return a + b

@register
@mcp.tool(tags=['math'])
def subtract(a: int, b: int) -> int:
    """Subtracts the second integer from the first."""
    print(f"Executing 'subtract' tool with a={a}, b={b}")
    return a - b

@register
@mcp.tool(tags=['math', 'advanced'])
def multiply(a: int, b: int) -> int:
    """Multiplies two integers."""
    print(f"Executing 'multiply' tool with a={a}, b={b}")
    return a * b

@register
@mcp.tool(tags=['text', 'basic'])
def reverse_string(text: str) -> str:
    """Reverses a given string."""
    print(f"Executing 'reverse_string' tool with text='{text}'")
    return text[::-1]

@register
@mcp.tool(tags=['text', 'advanced'])
def concatenate_strings(items: List[str], separator: str = ' ') -> str:
    """Joins a list of strings with a separator."""
    print(f"Executing 'concatenate_strings' tool")
    return separator.join(items)

@register
@mcp.tool(tags=['info', 'basic'])
def get_server_time() -> str:
    """Returns the current UTC time on the server."""
    print(f"Executing 'get_server_time' tool")
    return datetime.utcnow().isoformat()


def get_all_tools() -> List:
    """Returns all tools from our self-managed registry."""
    return TOOL_REGISTRY


@register
@mcp.tool(tags=['discovery'])
def list_tools_by_tag(tag: str) -> str:
    """
    Lists all available tools associated with a specific tag.
    Returns a JSON string to ensure reliable communication.
    """
    print(f"Executing 'list_tools_by_tag' for tag='{tag}'")
    tagged_tools = []
    all_tools = get_all_tools()
    for tool_object in all_tools:
        # Access the 'tags' and 'name' attributes of the tool object
        if tool_object.tags and tag in tool_object.tags:
            tagged_tools.append(tool_object.name)

    response_dict = {
        "tag_queried": tag,
        "available_tools": tagged_tools
    }
    # Return response as a JSON string to avoid serialization issues
    return json.dumps(response_dict)


def main():
    """Main function to configure and run the server."""
    print("🚀 FastMCP Tagged Server (HTTP)")
    print("=" * 50)
    print("Available Tools:")
    all_tools = get_all_tools()
    for tool in all_tools:
        # Access the 'tags' and 'name' attributes of the tool object
        tags = tool.tags or ['No Tags']
        print(f"  - {tool.name} (Tags: {', '.join(tags)})")
    print("=" * 50)
    print("Starting server on http://0.0.0.0:8000")

    mcp.run(
        transport="sse",
        host="0.0.0.0",
        port=8000,
    )

if __name__ == "__main__":
    main()
