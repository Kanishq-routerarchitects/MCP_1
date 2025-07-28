import asyncio
import json
from typing import List
from fastmcp import Client

# --- Client Configuration ---
SERVER_URL = "http://localhost:8000"

async def interactive_client():
    """An interactive client to connect to the tagged MCP server."""

    print("🚀 FastMCP Tagged Client (HTTP)")
    print("=" * 50)

    try:
        # Connect to the HTTP server (no SSL context needed)
        async with Client(f"{SERVER_URL}/sse") as client:
            print(f"✅ Connected successfully to {SERVER_URL}")

            while True:
                # --- Stage 1: Choose a Tag ---
                print("\n--- Step 1: Select a Tool Group (Tag) ---")
                tag_choice = input("Enter a tag (e.g., 'math', 'text', 'basic', 'advanced', 'info'): ").strip().lower()
                if not tag_choice:
                    print("Exiting. Goodbye!")
                    break

                # --- Stage 2: Discover Tools for the Tag ---
                print(f"\n🔍 Discovering tools for tag: '{tag_choice}'...")
                try:
                    # The server returns a JSON string, but the library might wrap it in its own object.
                    raw_response = await client.call_tool("list_tools_by_tag", {"tag": tag_choice})
                    
                    json_string = None
                    
                    # Determine the core object, whether it's in a list or standalone.
                    core_object = raw_response
                    if isinstance(raw_response, list) and len(raw_response) > 0:
                        core_object = raw_response[0]

                    # Intelligently extract the string content.
                    # First, check for a .text attribute, which is common for response objects.
                    if hasattr(core_object, 'text'):
                        json_string = core_object.text
                    else:
                        # If no .text attribute, fall back to converting the object to a string.
                        json_string = str(core_object)

                    if not json_string:
                        raise ValueError("Received an empty or invalid response from the server.")

                    # For debugging: print the exact string we are about to parse.
                    # The !r shows the representation, including any quotes.
                    print(f"DEBUG: Attempting to parse JSON: {json_string!r}")

                    # We must parse the JSON string back into a dictionary
                    response = json.loads(json_string)
                    
                    available_tools = response.get("available_tools", [])

                    if not available_tools:
                        print(f"❌ No tools found for tag '{tag_choice}'. Please try another tag.")
                        continue

                    print(f"✅ Found tools: {', '.join(available_tools)}")

                except json.JSONDecodeError:
                    print(f"❌ Error: Received an invalid JSON response from the server.")
                    continue
                except Exception as e:
                    print(f"Error discovering tools: {e}")
                    continue

                # --- Stage 3: Choose and Execute a Tool ---
                print("\n--- Step 2: Choose and Execute a Tool ---")
                tool_to_run = input(f"Enter the name of the tool to run from the list above: ").strip()

                if tool_to_run not in available_tools:
                    print(f"❌ Invalid tool name. Please choose from: {', '.join(available_tools)}")
                    continue
                
                params = {}
                # Get parameters based on the chosen tool
                if tool_to_run in ['add', 'subtract', 'multiply']:
                    params['a'] = int(input("Enter first number (a): "))
                    params['b'] = int(input("Enter second number (b): "))
                elif tool_to_run == 'reverse_string':
                    params['text'] = input("Enter the string to reverse: ")
                elif tool_to_run == 'concatenate_strings':
                    items_str = input("Enter strings to join, separated by commas: ")
                    params['items'] = [item.strip() for item in items_str.split(',')]
                    params['separator'] = input("Enter a separator (press Enter for space): ") or ' '
                elif tool_to_run == 'get_server_time':
                    # This tool takes no parameters
                    pass

                # Execute the chosen tool
                try:
                    print(f"\n🚀 Executing '{tool_to_run}' with params: {params}...")
                    result = await client.call_tool(tool_to_run, params)
                    print("-" * 20)
                    print(f"🎉 Result: {result}")
                    print("-" * 20)
                except Exception as e:
                    print(f"❌ Error executing tool: {e}")

                # Ask to continue
                if input("\nPress Enter to continue, or type 'exit' to quit: ").strip().lower() == 'exit':
                    break

    except ConnectionRefusedError:
        print(f"❌ Connection Error: Could not connect to the server at {SERVER_URL}.")
        print("   Please ensure the server.py script is running.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")


if __name__ == "__main__":
    try:
        asyncio.run(interactive_client())
    except KeyboardInterrupt:
        print("\nClient stopped by user.")
