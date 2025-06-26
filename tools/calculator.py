from fastmcp.tool import Tool

class CalculatorTool(Tool):
    def run(self, tool_input: dict, **kwargs):
        expr = tool_input.get("expression", "")
        try:
            result = eval(expr, {}, {})  # ⚠️ Safe only for demo
            return {"result": result}
        except Exception as e:
            return {"error": str(e)}
