from fastmcp.tool import Tool

class WebSearchTool(Tool):
    def run(self, tool_input: dict, **kwargs):
        query = tool_input.get("query", "")
        return {
            "results": [
                f"Mock result 1 for '{query}'",
                f"Mock result 2 for '{query}'"
            ]
        }
