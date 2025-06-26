from fastmcp.tool import Tool

class EchoTool(Tool):
    def run(self, tool_input: dict, **kwargs):
        return {"echo": tool_input}
