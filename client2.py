#!/usr/bin/env python3

import asyncio
import aiohttp
import json
import os
import signal
import sys
import time
import uuid
from typing import Dict, List, Optional, Any, Union
from datetime import datetime

try:
    import groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False


class GroqClient:
    """Enhanced Groq client for AI-powered analysis"""
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        if not self.api_key or not GROQ_AVAILABLE:
            print("⚠️ Warning: No Groq API key provided or groq package not installed. Using fallback analysis.")
            self.client = None
        else:
            self.client = groq.Groq(api_key=self.api_key)
        self.model = "llama3-70b-8192"

    async def analyze_query(self, user_query: str, available_tools: List[str]) -> Dict[str, Any]:
        """Analyze user query and suggest appropriate tools"""
        if not self.client:
            return self._fallback_analysis(user_query, available_tools)
        
        try:
            tools_list = ", ".join(available_tools)
            prompt = f"""
            Analyze this user query and determine the best approach:
            
            Query: "{user_query}"
            Available tools: {tools_list}
            
            Priority order:
            1. API tools (calculator, weather_info, currency_converter, time_info, text_analyzer)
            2. Database tools (list_tables, describe_table, execute_query, count_records, table_sample)
            
            Return a JSON response with:
            {{
                "tool_type": "api" or "database",
                "recommended_tool": "tool_name",
                "confidence": 0.0-1.0,
                "reasoning": "why this tool",
                "parameters": {{"param": "value"}},
                "alternative_tools": ["tool1", "tool2"]
            }}
            """
            
            response = self.client.chat.completions.create(
                messages=[
                    {"role": "system", "content": "You are a tool selection expert. Always respond with valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                model=self.model,
                max_tokens=512,
                temperature=0.1
            )
            
            result = response.choices[0].message.content
            try:
                return json.loads(result)
            except json.JSONDecodeError:
                return self._fallback_analysis(user_query, available_tools)
                
        except Exception as e:
            print(f"⚠️ Groq analysis failed: {e}")
            return self._fallback_analysis(user_query, available_tools)
    
    def _fallback_analysis(self, user_query: str, available_tools: List[str]) -> Dict[str, Any]:
        """Fallback analysis when Groq is not available"""
        query_lower = user_query.lower()
        
        # API tool patterns with better matching
        api_patterns = {
            "calculator": ["calculate", "math", "compute", "+", "-", "*", "/", "=", "plus", "minus", "multiply", "divide", "solve", "?"],
            "weather_info": ["weather", "temperature", "climate", "forecast", "rain", "sunny", "cloudy", "humidity"],
            "currency_converter": ["convert", "currency", "exchange", "rate", "usd", "eur", "inr", "gbp", "dollar"],
            "time_info": ["time", "date", "today", "now", "when", "clock", "current"],
            "text_analyzer": ["analyze", "text", "words", "count", "characters", "sentences", "paragraphs"]
        }
        
        # Database tool patterns
        db_patterns = {
            "list_tables": ["tables", "list", "show tables", "what tables", "available tables", "database tables"],
            "describe_table": ["describe", "structure", "columns", "schema", "table structure", "fields", "customer", "customers"],
            "execute_query": ["select", "query", "sql", "from", "where", "join", "group by", "get", "find", "all"],
            "count_records": ["count", "how many", "number of", "total", "records", "rows"],
            "table_sample": ["sample", "example", "few", "preview", "show me", "data"]
        }
        
        # Check API tools first (higher priority)
        best_match = None
        best_score = 0
        
        for tool, patterns in api_patterns.items():
            if tool in available_tools:
                score = sum(1 for pattern in patterns if pattern in query_lower)
                if score > best_score:
                    best_score = score
                    best_match = tool
        
        # If no API match, check database tools
        if best_match is None:
            for tool, patterns in db_patterns.items():
                if tool in available_tools:
                    score = sum(1 for pattern in patterns if pattern in query_lower)
                    if score > best_score:
                        best_score = score
                        best_match = tool
        
        # Default to first available tool if no match
        if best_match is None and available_tools:
            best_match = available_tools[0]
        
        # Generate parameters based on tool
        parameters = {}
        if best_match == "calculator":
            # Extract mathematical expression
            import re
            math_pattern = r'[0-9+\-*/().\s]+'
            matches = re.findall(math_pattern, user_query)
            if matches:
                parameters["expression"] = max(matches, key=len).strip()
            else:
                parameters["expression"] = user_query
        
        elif best_match == "weather_info":
            # Extract city name
            words = user_query.split()
            for i, word in enumerate(words):
                if word.lower() in ["in", "for", "of"]:
                    if i + 1 < len(words):
                        parameters["city"] = words[i + 1]
                        break
            if "city" not in parameters:
                parameters["city"] = "Mumbai"  # Default
        
        elif best_match == "currency_converter":
            # Extract currency info
            words = user_query.split()
            amount = None
            from_curr = None
            to_curr = None
            
            for word in words:
                if word.replace('.', '').isdigit():
                    amount = float(word)
                elif word.upper() in ["USD", "EUR", "INR", "GBP"]:
                    if from_curr is None:
                        from_curr = word.upper()
                    else:
                        to_curr = word.upper()
            
            parameters["amount"] = amount or 100
            parameters["from_currency"] = from_curr or "USD"
            parameters["to_currency"] = to_curr or "INR"
        
        elif best_match == "text_analyzer":
            # Use the query itself as text to analyze
            parameters["text"] = user_query
        
        elif best_match == "time_info":
            parameters["timezone"] = "UTC"
        
        elif best_match == "describe_table":
            # Extract table name
            words = user_query.split()
            table_name = None
            for word in words:
                if word.lower() not in ["describe", "table", "structure", "of", "the"]:
                    table_name = word
                    break
            parameters["table_name"] = table_name or "customers"
        
        elif best_match == "execute_query":
            # Use the query as SQL
            parameters["query"] = user_query
        
        elif best_match == "count_records":
            # Extract table name
            words = user_query.split()
            table_name = None
            for word in words:
                if word.lower() not in ["count", "how", "many", "records", "in", "the"]:
                    table_name = word
                    break
            parameters["table_name"] = table_name or "customers"
        
        elif best_match == "table_sample":
            # Extract table name
            words = user_query.split()
            table_name = None
            for word in words:
                if word.lower() not in ["sample", "from", "show", "me", "data", "the"]:
                    table_name = word
                    break
            parameters["table_name"] = table_name or "customers"
            parameters["sample_size"] = 5
        
        return {
            "tool_type": "api" if best_match in api_patterns else "database",
            "recommended_tool": best_match or "calculator",
            "confidence": min(best_score / 5.0, 1.0),
            "reasoning": f"Pattern matching found {best_score} keywords",
            "parameters": parameters,
            "alternative_tools": [tool for tool in available_tools if tool != best_match][:3]
        }


class FastMCPClient:
    """FastMCP Client with intelligent tool selection"""
    
    def __init__(self, server_url: str = "http://localhost:8000", debug: bool = True):
        self.server_url = server_url.rstrip('/')
        self.session = None
        self.connection_id = str(uuid.uuid4())
        self.groq_client = GroqClient()
        self.available_tools = []
        self.running = False
        self.debug = debug
        
    async def __aenter__(self):
        """Async context manager entry"""
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()
    
    async def connect(self):
        """Connect to the FastMCP server"""
        try:
            # Test server connection
            async with self.session.get(f"{self.server_url}/health") as response:
                if response.status == 200:
                    health_data = await response.json()
                    print(f"✅ Connected to FastMCP Server")
                    print(f"   Status: {health_data['status']}")
                    print(f"   Database: {health_data['database']}")
                    print(f"   Tools: {health_data['tools']}")
                else:
                    raise Exception(f"Server health check failed: {response.status}")
            
            # Get available tools
            await self.fetch_tools()
            
            return True
            
        except Exception as e:
            print(f"❌ Connection failed: {e}")
            return False
    
    async def fetch_tools(self):
        """Fetch available tools from server"""
        try:
            async with self.session.get(f"{self.server_url}/tools") as response:
                if response.status == 200:
                    tools_data = await response.json()
                    self.available_tools = [tool["name"] for tool in tools_data["tools"]]
                    print(f"🔧 Available tools: {', '.join(self.available_tools)}")
                else:
                    print(f"⚠️ Failed to fetch tools: {response.status}")
        except Exception as e:
            print(f"⚠️ Error fetching tools: {e}")
    
    async def call_tool(self, tool_name: str, **kwargs) -> Dict[str, Any]:
        """Call a tool on the server"""
        try:
            request_data = {
                "jsonrpc": "2.0",
                "id": int(time.time()),
                "method": "tools/call",
                "params": {
                    "name": tool_name,
                    "arguments": kwargs
                }
            }
            
            if self.debug:
                print(f"🔧 Sending request: {json.dumps(request_data, indent=2)}")
            
            async with self.session.post(
                f"{self.server_url}/mcp",
                json=request_data,
                headers={"Content-Type": "application/json"}
            ) as response:
                response_text = await response.text()
                
                if self.debug:
                    print(f"📥 Raw response ({response.status}): {response_text}")
                
                if response.status == 200:
                    try:
                        result = json.loads(response_text)
                        
                        if self.debug:
                            print(f"📋 Parsed response: {json.dumps(result, indent=2)}")
                        
                        if "error" in result and result["error"]:
                            return {"error": result["error"]["message"]}
                        elif "result" in result:
                            return result["result"]
                        else:
                            return {"error": "Unexpected response format", "raw": result}
                    except json.JSONDecodeError as e:
                        return {"error": f"JSON decode error: {e}", "raw": response_text}
                else:
                    return {"error": f"HTTP {response.status}: {response_text}"}
                    
        except Exception as e:
            return {"error": f"Request failed: {str(e)}"}
    
    async def test_direct_call(self, tool_name: str, **kwargs) -> Dict[str, Any]:
        """Test direct tool call without MCP protocol (for debugging)"""
        try:
            # Try direct endpoint if available
            test_data = {"tool": tool_name, "params": kwargs}
            
            async with self.session.post(
                f"{self.server_url}/test_tool",
                json=test_data,
                headers={"Content-Type": "application/json"}
            ) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    return {"error": f"Direct call failed: HTTP {response.status}"}
                    
        except Exception as e:
            return {"error": f"Direct call error: {str(e)}"}
    
    async def simple_tool_test(self):
        """Simple tool testing without MCP protocol"""
        print("\n🧪 Testing tools directly...")
        
        # Test calculator
        print("\n📊 Testing calculator...")
        result = await self.test_direct_call("calculator", expression="2+2")
        print(f"Result: {result}")
        
        # Test weather
        print("\n🌤️ Testing weather...")
        result = await self.test_direct_call("weather_info", city="Mumbai")
        print(f"Result: {result}")
        
        # Test database
        print("\n🗃️ Testing database...")
        result = await self.test_direct_call("list_tables")
        print(f"Result: {result}")
    
    async def intelligent_query(self, user_query: str) -> Dict[str, Any]:
        """Process user query with intelligent tool selection"""
        print(f"\n🤔 Analyzing query: '{user_query}'")
        
        # Analyze query with Groq or fallback
        analysis = await self.groq_client.analyze_query(user_query, self.available_tools)
        
        print(f"🎯 Analysis result:")
        print(f"   Tool: {analysis['recommended_tool']}")
        print(f"   Confidence: {analysis['confidence']:.2f}")
        print(f"   Reasoning: {analysis['reasoning']}")
        
        # Execute the recommended tool
        tool_name = analysis["recommended_tool"]
        parameters = analysis["parameters"]
        
        print(f"⚡ Executing {tool_name} with parameters: {parameters}")
        
        result = await self.call_tool(tool_name, **parameters)
        
        return {
            "query": user_query,
            "analysis": analysis,
            "result": result
        }
    
    async def interactive_mode(self):
        """Interactive command-line mode"""
        print("\n🚀 FastMCP Interactive Client")
        print("=" * 50)
        print("Commands:")
        print("  • Type any query to get intelligent tool selection")
        print("  • 'tools' - List available tools")
        print("  • 'debug' - Toggle debug mode")
        print("  • 'test' - Run simple tool tests")
        print("  • 'help' - Show this help")
        print("  • 'quit' or 'exit' - Exit the client")
        print("=" * 50)
        
        self.running = True
        
        while self.running:
            try:
                user_input = input("\n💬 Query: ").strip()
                
                if not user_input:
                    continue
                
                if user_input.lower() in ['quit', 'exit', 'q']:
                    print("👋 Goodbye!")
                    break
                
                elif user_input.lower() == 'tools':
                    print(f"🔧 Available tools: {', '.join(self.available_tools)}")
                    continue
                
                elif user_input.lower() == 'debug':
                    self.debug = not self.debug
                    print(f"🔧 Debug mode: {'ON' if self.debug else 'OFF'}")
                    continue
                
                elif user_input.lower() == 'test':
                    await self.simple_tool_test()
                    continue
                
                elif user_input.lower() == 'help':
                    print("\n📖 Help:")
                    print("  • Calculator: '2 + 2', 'sqrt(16)', 'cos(0)'")
                    print("  • Weather: 'weather in Mumbai', 'temperature in Delhi'")
                    print("  • Currency: 'convert 100 USD to INR'")
                    print("  • Time: 'current time', 'what time is it'")
                    print("  • Text: 'analyze this text'")
                    print("  • Database: 'list tables', 'describe customers', 'select * from orders'")
                    continue
                
                # Process the query
                start_time = time.time()
                response = await self.intelligent_query(user_input)
                end_time = time.time()
                
                # Display results
                print(f"\n📊 Results (took {end_time - start_time:.2f}s):")
                print("-" * 40)
                
                if "error" in response["result"]:
                    print(f"❌ Error: {response['result']['error']}")
                    if "raw" in response["result"]:
                        print(f"🔍 Raw response: {response['result']['raw']}")
                else:
                    # Handle different response formats
                    result_data = response["result"]
                    
                    if isinstance(result_data, dict):
                        if "content" in result_data and result_data["content"]:
                            # Standard MCP format
                            if isinstance(result_data["content"], list) and len(result_data["content"]) > 0:
                                content = result_data["content"][0].get("text", str(result_data["content"][0]))
                                print(content)
                            else:
                                print(str(result_data["content"]))
                        else:
                            # Direct result format
                            print(json.dumps(result_data, indent=2))
                    else:
                        # Simple string or other format
                        print(str(result_data))
                
                # Show alternatives if confidence is low
                if response["analysis"]["confidence"] < 0.5:
                    alternatives = response["analysis"]["alternative_tools"]
                    if alternatives:
                        print(f"\n💡 Other tools you might try: {', '.join(alternatives)}")
                
            except KeyboardInterrupt:
                print("\n\n👋 Goodbye!")
                break
            except Exception as e:
                print(f"❌ Error: {e}")
    
    def stop(self):
        """Stop the client"""
        self.running = False


async def main():
    """Main function"""
    # Handle graceful shutdown
    def signal_handler(signum, frame):
        print("\n🛑 Shutting down...")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Get configuration from environment
    server_url = os.getenv("FASTMCP_SERVER_URL", "http://localhost:8000")
    debug_mode = os.getenv("DEBUG", "false").lower() == "true"
    
    print("🌟 FastMCP Client Starting...")
    print(f"🌐 Server URL: {server_url}")
    print(f"🔧 Debug Mode: {'ON' if debug_mode else 'OFF'}")
    
    # Create and run client
    async with FastMCPClient(server_url, debug=debug_mode) as client:
        if await client.connect():
            await client.interactive_mode()
        else:
            print("❌ Failed to connect to server")
            sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        sys.exit(1)