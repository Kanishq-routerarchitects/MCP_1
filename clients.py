import asyncio
import os
import logging
from typing import List, Tuple
from pydantic_ai import Agent
from pydantic_ai.mcp import MCPServerSSE
from dotenv import load_dotenv
import logfire

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s"
)
logger = logging.getLogger("mcp-client")

logfire.configure(token='pylf_v1_us_nMpfjtYYWMgylZzJ5yTTmJgd47MVqlmKrhBlfDlY8ghY')
logfire.instrument_pydantic_ai()

load_dotenv()

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
MCP_SERVER_URL = "http://localhost:8000/sse"

async def chat_with_agent(prompt: str) -> Tuple[List[str], str]:
    """
    Process user prompt and return tools used with response.
    
    Returns:
        Tuple containing:
        - List of tool names used
        - Final agent response
    """
    tools_used = []
    response = ''
    
    try:
        server = MCPServerSSE(url=MCP_SERVER_URL)
        agent = Agent(
            model="groq:llama3-70b-8192",
            api_key=GROQ_API_KEY,
            mcp_servers=[server]
        )
        
        async with agent.run_mcp_servers():
            agent_result = await agent.run(prompt)
            
            # Check messages for tool calls
            print(f"\n=== DEBUG INFO ===")
            
            # Get messages - they might be methods, so call them
            try:
                if hasattr(agent_result, 'all_messages'):
                    if callable(agent_result.all_messages):
                        all_messages = agent_result.all_messages()
                    else:
                        all_messages = agent_result.all_messages
                    
                    print(f"All messages count: {len(all_messages)}")
                    for i, msg in enumerate(all_messages):
                        print(f"\nMessage {i}: {type(msg).__name__}")
                        
                        # Check the parts attribute for tool calls
                        if hasattr(msg, 'parts') and msg.parts:
                            print(f"  Parts count: {len(msg.parts)}")
                            for j, part in enumerate(msg.parts):
                                print(f"    Part {j}: {type(part).__name__}")
                                print(f"    Part {j} attributes: {[attr for attr in dir(part) if not attr.startswith('_')]}")
                                
                                # Check if this part is a tool call
                                if hasattr(part, 'tool_name'):
                                    tool_name = part.tool_name
                                    print(f"    Found tool_name: {tool_name}")
                                    if tool_name not in tools_used:
                                        tools_used.append(tool_name)
                                        print(f"    Added tool: {tool_name}")
                                
                                # Check for other tool-related attributes
                                for attr in ['name', 'function_name', 'tool_call_id']:
                                    if hasattr(part, attr):
                                        value = getattr(part, attr)
                                        print(f"    {attr}: {value}")
                                
                                # Print the actual part content if it's small
                                try:
                                    part_str = str(part)
                                    if len(part_str) < 200:
                                        print(f"    Part content: {part_str}")
                                    else:
                                        print(f"    Part content: {part_str[:200]}...")
                                except:
                                    pass
                        else:
                            print(f"  No parts or empty parts")
                
            except Exception as e:
                print(f"Error in debug: {e}")
                import traceback
                traceback.print_exc()
            
            print(f"\nFinal tools_used: {tools_used}")
            print(f"=== END DEBUG ===\n")
            
            response = agent_result.output
            
        return tools_used, response
        
    except Exception as e:
        logger.error(f"Error processing prompt: {str(e)}")
        return [], f"Error occurred: {str(e)}"

async def main():
    """Interactive chat interface with array output"""
    print("\n=== Tool-Enabled Chat Agent ===")
    print("Type 'exit' to quit\n")
    
    while True:
        user_input = input("You: ").strip()
        
        if user_input.lower() in ["exit", "quit", "bye"]:
            print("\nGoodbye!")
            break
        
        tools_used, response = await chat_with_agent(user_input)
        
        # Output as array format
        result_array = [tools_used, response]
        print(f"\nResult: {result_array}\n")

if __name__ == "__main__":
    asyncio.run(main())