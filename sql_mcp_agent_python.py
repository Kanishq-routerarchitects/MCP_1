import os
import sys
import json
import subprocess
import threading
import time
import signal
from pathlib import Path
from typing import Dict, List, Optional, Any, Union

class CustomSQLMCPAgent:
    def __init__(self, mcp_server_path: str, connection_config: Dict[str, Any]):
        self.mcp_server_path = mcp_server_path
        self.connection_config = connection_config
        self.mcp_process: Optional[subprocess.Popen] = None
        self.available_tools: List[Dict[str, Any]] = []
        self.pending_requests: Dict[int, Dict[str, Any]] = {}
        self.request_id_counter = 1
        self.config_path: Optional[str] = None

    async def initialize(self):
        print('🚀 Initializing Custom SQL MCP Agent...')

        try:
            await self.create_config_file()
            await self.start_mcp_server()
            await self.sleep(3000)  # Give server time to fully start
            await self.initialize_mcp_protocol()
            await self.discover_tools()

            print('✅ MCP Agent initialized successfully!')
            print(f'📊 Connected to database: {self.connection_config["database"]}')
            print(f'🛠️  Available tools: {len(self.available_tools)}')
        except Exception as error:
            print(f'❌ Failed to initialize MCP Agent: {str(error)}')
            raise error

    async def create_config_file(self):
        """Create a temporary configuration file that the MCP server can read"""
        config_path = Path(__file__).parent / 'temp_mcp_config.json'
        config = {
            "server": self.connection_config["server"],
            "database": self.connection_config["database"],
            "user": self.connection_config["user"],
            "password": self.connection_config["password"],
            "port": self.connection_config.get("port", 1433),
            "options": {
                "encrypt": self.connection_config.get("options", {}).get("encrypt", True) is not False,
                "trustServerCertificate": self.connection_config.get("options", {}).get("trustServerCertificate", True) is not False
            }
        }

        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
        
        self.config_path = str(config_path)
        print(f'📝 Created temporary config file: {self.config_path}')

    async def sleep(self, ms: int):
        await asyncio.sleep(ms / 1000)

    async def start_mcp_server(self):
        """Start the MCP server process"""
        # Prepare environment variables
        env = os.environ.copy()
        env.update({
            # Standard environment variables
            "MSSQL_SERVER": self.connection_config["server"],
            "MSSQL_USER": self.connection_config["user"],
            "MSSQL_PASSWORD": self.connection_config["password"],
            "MSSQL_DATABASE": self.connection_config["database"],
            "MSSQL_PORT": str(self.connection_config.get("port", 1433)),
            "MSSQL_ENCRYPT": str(self.connection_config.get("options", {}).get("encrypt", True) is not False),
            "MSSQL_TRUST_SERVER_CERTIFICATE": str(self.connection_config.get("options", {}).get("trustServerCertificate", True) is not False),
            
            # Alternative patterns
            "DB_SERVER": self.connection_config["server"],
            "DB_USER": self.connection_config["user"],
            "DB_PASSWORD": self.connection_config["password"],
            "DB_DATABASE": self.connection_config["database"],
            "DB_PORT": str(self.connection_config.get("port", 1433)),
            
            # Connection string format
            "DATABASE_URL": f"Server={self.connection_config['server']};Database={self.connection_config['database']};"
                            f"User Id={self.connection_config['user']};Password={self.connection_config['password']};"
                            "TrustServerCertificate=true;Encrypt=true;"
        })

        print('Starting MCP server with config:', {
            "server": self.connection_config["server"],
            "database": self.connection_config["database"],
            "user": self.connection_config["user"],
            "serverPath": self.mcp_server_path
        })

        # Prepare command arguments
        args = ["node", self.mcp_server_path]
        
        if self.config_path:
            args.extend(['--config', self.config_path])

        try:
            self.mcp_process = subprocess.Popen(
                args,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                cwd=str(Path(self.mcp_server_path).parent),
                text=True,
                bufsize=1,
                universal_newlines=True
            )

            # Start threads to handle stdout and stderr
            threading.Thread(target=self._handle_mcp_stdout, daemon=True).start()
            threading.Thread(target=self._handle_mcp_stderr, daemon=True).start()

            # Wait briefly to check if process started
            await self.sleep(2000)
            if self.mcp_process.poll() is not None:
                raise Exception(f"MCP server failed to start. Exit code: {self.mcp_process.returncode}")

        except Exception as error:
            raise Exception(f"Failed to start MCP server: {str(error)}")

    def _handle_mcp_stdout(self):
        """Handle stdout from the MCP server process"""
        if self.mcp_process and self.mcp_process.stdout:
            for line in iter(self.mcp_process.stdout.readline, ''):
                line = line.strip()
                if line:
                    print(f'MCP Server Output: {line}')
                    self.handle_mcp_response(line)

    def _handle_mcp_stderr(self):
        """Handle stderr from the MCP server process"""
        if self.mcp_process and self.mcp_process.stderr:
            for line in iter(self.mcp_process.stderr.readline, ''):
                line = line.strip()
                if line:
                    print(f'MCP Server Error: {line}', file=sys.stderr)
                    # Check for specific configuration errors
                    if "config.server" in line or "configuration" in line:
                        print(f"MCP Server configuration error: {line}", file=sys.stderr)

    async def initialize_mcp_protocol(self):
        print('Initializing MCP protocol...')
        init_message = {
            "jsonrpc": "2.0",
            "id": self.get_next_request_id(),
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "roots": {"listChanged": True},
                    "sampling": {}
                },
                "clientInfo": {
                    "name": "Custom SQL MCP Agent",
                    "version": "1.0.0"
                }
            }
        }

        try:
            response = await self.send_mcp_message(init_message)
            print('MCP protocol initialized:', 'Success' if response.get('result') else 'Failed')
            
            # Send initialized notification
            initialized_message = {
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
                "params": {}
            }
            
            self.send_mcp_notification(initialized_message)
        except Exception as error:
            print(f'Failed to initialize MCP protocol: {str(error)}')
            raise error

    def get_next_request_id(self) -> int:
        self.request_id_counter += 1
        return self.request_id_counter

    async def discover_tools(self):
        print('Discovering available tools...')
        tools_message = {
            "jsonrpc": "2.0",
            "id": self.get_next_request_id(),
            "method": "tools/list",
            "params": {}
        }

        try:
            response = await self.send_mcp_message(tools_message)

            if response and response.get('result', {}).get('tools'):
                self.available_tools = response['result']['tools']
                print('\n📋 Available Database Tools:')
                for tool in self.available_tools:
                    print(f'   • {tool["name"]}: {tool["description"]}')
            else:
                print('No tools discovered. Response:', json.dumps(response, indent=2))
                await self.try_alternative_tool_discovery()
        except Exception as error:
            print(f'Error discovering tools: {str(error)}')
            raise error

    async def try_alternative_tool_discovery(self):
        print('Trying alternative tool discovery methods...')
        methods = ['tools/list', 'list_tools', 'get_tools', 'capabilities']
        
        for method in methods:
            try:
                response = await self.send_mcp_message({
                    "jsonrpc": "2.0",
                    "id": self.get_next_request_id(),
                    "method": method,
                    "params": {}
                })
                
                if response and response.get('result'):
                    print(f'Method {method} returned:', json.dumps(response['result'], indent=2))
            except Exception as error:
                print(f'Method {method} failed: {str(error)}')

    async def send_mcp_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        loop = asyncio.get_event_loop()
        future = loop.create_future()
        
        message_str = json.dumps(message) + '\n'
        
        if not self.mcp_process or self.mcp_process.poll() is not None:
            raise Exception('MCP process not available')

        print('Sending MCP message:', json.dumps(message, indent=2))

        try:
            self.mcp_process.stdin.write(message_str)
            self.mcp_process.stdin.flush()
            
            self.pending_requests[message['id']] = {
                'future': future,
                'timestamp': time.time()
            }

            # Set timeout for request
            def timeout_callback():
                if message['id'] in self.pending_requests:
                    del self.pending_requests[message['id']]
                    future.set_exception(Exception(f"Request timeout for message ID: {message['id']}"))

            loop.call_later(15, timeout_callback)
            
            return await future
        except Exception as error:
            raise Exception(f"Failed to send message: {str(error)}")

    def send_mcp_notification(self, message: Dict[str, Any]):
        message_str = json.dumps(message) + '\n'
        print('Sending MCP notification:', json.dumps(message, indent=2))
        
        if self.mcp_process and self.mcp_process.poll() is None:
            try:
                self.mcp_process.stdin.write(message_str)
                self.mcp_process.stdin.flush()
            except Exception as error:
                print(f'Failed to send notification: {str(error)}')

    def handle_mcp_response(self, data: str):
        try:
            if not data.strip():
                return

            try:
                response = json.loads(data)
                print('Received MCP response:', json.dumps(response, indent=2))
                
                # Handle responses with IDs (requests)
                if 'id' in response and response['id'] in self.pending_requests:
                    future = self.pending_requests[response['id']]['future']
                    del self.pending_requests[response['id']]
                    
                    if 'error' in response:
                        future.set_exception(Exception(response['error'].get('message', json.dumps(response['error']))))
                    else:
                        future.set_result(response)
                # Handle errors
                elif 'error' in response:
                    print('MCP Error Response:', response['error'])
                # Handle notifications (no ID)
                elif 'method' in response:
                    print(f'MCP Notification: {response["method"]} {response.get("params", {})}')
            except json.JSONDecodeError:
                print('Non-JSON output from MCP server:', data)
        except Exception as error:
            print(f'Error handling MCP response: {str(error)}')
            print('Raw data:', data)

    async def process_natural_language_query(self, user_input: str):
        print(f'\n🤔 Processing: "{user_input}"')

        if not self.available_tools:
            print('❌ No tools available. Please check MCP server connection.')
            return

        analysis = self.analyze_user_input(user_input)
        print(f'🎯 Intent: {analysis["intent"]}')
        print(f'🗂️  Target Tables: {", ".join(analysis["tables"]) if analysis["tables"] else "Auto-detect"}')

        try:
            result = await self.execute_analysis(analysis)
            self.display_results(result, user_input)
        except Exception as error:
            print(f'❌ Error processing query: {str(error)}')

    def analyze_user_input(self, input_str: str) -> Dict[str, Any]:
        input_lower = input_str.lower()

        intent = 'SELECT'
        if any(word in input_lower for word in ['show', 'list', 'get', 'find', 'select', 'display']):
            intent = 'SELECT'
        elif any(word in input_lower for word in ['count', 'how many', 'total']):
            intent = 'COUNT'
        elif any(word in input_lower for word in ['create', 'add', 'insert']):
            intent = 'INSERT'
        elif any(word in input_lower for word in ['update', 'change', 'modify']):
            intent = 'UPDATE'
        elif any(word in input_lower for word in ['delete', 'remove', 'drop']):
            intent = 'DELETE'
        elif any(word in input_lower for word in ['describe', 'structure', 'schema', 'columns']):
            intent = 'DESCRIBE'

        tables = []
        table_keywords = {
            'customers': ['customer', 'client', 'user'],
            'orders': ['order', 'purchase', 'sale'],
            'products': ['product', 'item'],
            'employees': ['employee', 'staff', 'worker'],
            'payments': ['payment', 'invoice', 'billing'],
            'support_tickets': ['ticket', 'issue', 'support']
        }

        for table, keywords in table_keywords.items():
            if any(keyword in input_lower for keyword in keywords):
                tables.append(table)

        conditions = {}
        
        # Extract location condition
        location_match = None
        for word in ['from', 'in']:
            if word in input_lower:
                parts = input_lower.split(word, 1)
                if len(parts) > 1:
                    location_match = parts[1].split()[0]
                    break
        
        if location_match:
            conditions['location'] = location_match.strip()

        # Extract limit condition
        limit_match = None
        for word in ['top', 'first', 'limit']:
            if word in input_lower:
                parts = input_lower.split(word, 1)
                if len(parts) > 1:
                    try:
                        limit_match = int(parts[1].split()[0])
                        break
                    except (ValueError, IndexError):
                        pass
        
        if limit_match:
            conditions['limit'] = limit_match

        # Extract status condition
        status_match = None
        for word in ['status', 'state']:
            if word in input_lower:
                parts = input_lower.split(word, 1)
                if len(parts) > 1:
                    status_match = parts[1].split()[0]
                    break
        
        if status_match:
            conditions['status'] = status_match

        return {
            "intent": intent,
            "tables": tables,
            "conditions": conditions,
            "originalInput": input_str
        }

    async def execute_analysis(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        intent = analysis["intent"]
        tables = analysis["tables"]
        conditions = analysis["conditions"]

        try:
            if intent == 'SELECT':
                if not tables:
                    return await self.list_all_tables()
                else:
                    return await self.read_table_data(tables[0], conditions)
            elif intent == 'COUNT':
                if tables:
                    return await self.count_table_records(tables[0], conditions)
                else:
                    return await self.list_all_tables()
            elif intent == 'DESCRIBE':
                if tables:
                    return await self.describe_table(tables[0])
                else:
                    return await self.list_all_tables()
            else:
                return await self.list_all_tables()
        except Exception as error:
            print(f'Error in execute_analysis: {str(error)}')
            raise error

    async def list_all_tables(self) -> Dict[str, Any]:
        tool_name = self.find_tool_by_name(['list_tables', 'list_table', 'show_tables', 'get_tables'])
        if not tool_name:
            print('Available tools:', [t["name"] for t in self.available_tools])
            raise Exception('No table listing tool found')

        return await self.send_mcp_message({
            "jsonrpc": "2.0",
            "id": self.get_next_request_id(),
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": {}
            }
        })

    async def describe_table(self, table_name: str) -> Dict[str, Any]:
        tool_name = self.find_tool_by_name(['describe_table', 'table_schema', 'show_columns', 'get_schema'])
        if not tool_name:
            raise Exception('No table description tool found')

        return await self.send_mcp_message({
            "jsonrpc": "2.0",
            "id": self.get_next_request_id(),
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": {"table_name": table_name}
            }
        })

    async def read_table_data(self, table_name: str, conditions: Dict[str, Any] = {}) -> Dict[str, Any]:
        tool_name = self.find_tool_by_name(['read_data', 'query_table', 'select_data', 'query'])
        if not tool_name:
            raise Exception('No data reading tool found')

        query = f'SELECT * FROM {table_name}'
        args = {}

        if conditions.get('where_clause'):
            query += f' WHERE {conditions["where_clause"]}'
        
        if conditions.get('limit'):
            query += f' LIMIT {conditions["limit"]}'
            args['limit'] = conditions['limit']
        
        if conditions.get('location'):
            args['where_clause'] = f"city LIKE '%{conditions['location']}%' OR state LIKE '%{conditions['location']}%'"
        
        if conditions.get('status'):
            status_clause = f"status = '{conditions['status']}'"
            args['where_clause'] = f"({args['where_clause']}) AND {status_clause}" if 'where_clause' in args else status_clause

        args['query'] = query

        return await self.send_mcp_message({
            "jsonrpc": "2.0",
            "id": self.get_next_request_id(),
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": args
            }
        })

    async def count_table_records(self, table_name: str, conditions: Dict[str, Any] = {}) -> Dict[str, Any]:
        tool_name = self.find_tool_by_name(['read_data', 'query_table', 'select_data', 'query'])
        if not tool_name:
            raise Exception('No data reading tool found')

        query = f'SELECT COUNT(*) as total_count FROM {table_name}'
        args = {}

        if conditions.get('where_clause'):
            query += f' WHERE {conditions["where_clause"]}'
        
        if conditions.get('location'):
            args['where_clause'] = f"city LIKE '%{conditions['location']}%' OR state LIKE '%{conditions['location']}%'"
        
        if conditions.get('status'):
            status_clause = f"status = '{conditions['status']}'"
            args['where_clause'] = f"({args['where_clause']}) AND {status_clause}" if 'where_clause' in args else status_clause

        args['query'] = query

        return await self.send_mcp_message({
            "jsonrpc": "2.0",
            "id": self.get_next_request_id(),
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": args
            }
        })

    def find_tool_by_name(self, possible_names: List[str]) -> Optional[str]:
        for name in possible_names:
            for tool in self.available_tools:
                if tool['name'] == name:
                    return tool['name']
        return None

    def display_results(self, result: Dict[str, Any], original_query: str):
        print('\n📊 Results:')
        print('─' * 50)

        if result and 'error' in result:
            print(f'❌ Error: {result["error"].get("message", result["error"])}')
        elif result and result.get('result', {}).get('content'):
            content = result['result']['content']
            if isinstance(content, list):
                for item in content:
                    if isinstance(item, dict) and item.get('type') == 'text':
                        print(item['text'])
                    else:
                        print(json.dumps(item, indent=2))
            elif isinstance(content, str):
                print(content)
            else:
                print(json.dumps(content, indent=2))
        else:
            print('No results returned')
            print('Full response:', json.dumps(result, indent=2))

        print('─' * 50)

    async def start_interactive_session(self):
        print('\n🎯 MCP Agent Ready!')
        print('💬 Try asking things like:')
        print('   • "Show me all tables"')
        print('   • "List orders from California"')
        print('   • "How many tickets are open?"')
        print('   • "Describe the customers table"')
        print('   • Type "tools" to see available tools')
        print('   • Type "exit" to quit\n')

        while True:
            try:
                user_input = input('🗣️  You: ').strip()
                
                if not user_input:
                    continue
                
                if user_input.lower() == 'exit':
                    print('👋 Closing MCP Agent...')
                    self.cleanup()
                    return
                
                if user_input.lower() == 'tools':
                    print('\n🛠️ Available Tools:')
                    if not self.available_tools:
                        print('   No tools discovered yet. This might indicate a connection issue.')
                    else:
                        for tool in self.available_tools:
                            print(f'   • {tool["name"]}: {tool["description"]}')
                    print('')
                    continue
                
                if user_input.lower() == 'debug':
                    print('\n🔍 Debug Information:')
                    print('MCP Process alive:', self.mcp_process and self.mcp_process.poll() is None)
                    print('Available tools:', len(self.available_tools))
                    print('Pending requests:', len(self.pending_requests))
                    print('')
                    continue
                
                await self.process_natural_language_query(user_input)
                print('\n')
                
            except KeyboardInterrupt:
                print('\n👋 Shutting down...')
                self.cleanup()
                return
            except Exception as error:
                print(f'Error: {str(error)}')

    def cleanup(self):
        print('Cleaning up resources...')
        
        # Clean up temporary config file
        if self.config_path and os.path.exists(self.config_path):
            try:
                os.unlink(self.config_path)
                print('Removed temporary config file')
            except Exception as error:
                print(f'Error removing config file: {str(error)}')
        
        if self.mcp_process and self.mcp_process.poll() is None:
            self.mcp_process.terminate()
            try:
                self.mcp_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.mcp_process.kill()
        
        sys.exit(0)

async def main():
    mcp_server_path = 'D:/MCP_server_client/SQL-AI-samples/MssqlMcp/Node/dist/index.js'

    connection_config = {
        "user": "sa",
        "password": "password",  # Update with your actual password
        "server": "localhost",
        "database": "testdb",
        "port": 1433,
        "options": {
            "encrypt": True,
            "trustServerCertificate": True
        }
    }

    print('🎯 Starting Custom SQL MCP Agent...')
    print('📋 Configuration:')
    print(f'   Server: {connection_config["server"]}:{connection_config["port"]}')
    print(f'   Database: {connection_config["database"]}')
    print(f'   User: {connection_config["user"]}')
    print(f'   MCP Server: {mcp_server_path}')

    agent = CustomSQLMCPAgent(mcp_server_path, connection_config)

    try:
        await agent.initialize()
        await agent.start_interactive_session()
    except Exception as error:
        print(f'Failed to start agent: {str(error)}')
        print('\n🔍 Troubleshooting Tips:')
        print('1. Verify the MCP server path exists and is correct')
        print('2. Check that your database is running and accessible')
        print('3. Verify your database credentials are correct')
        print('4. Make sure the MCP server supports the expected configuration format')
        print('5. Check if the MCP server needs to be built first (npm run build)')
        
        sys.exit(1)

def signal_handler(sig, frame):
    print('\n👋 Shutting down...')
    sys.exit(0)

if __name__ == '__main__':
    import asyncio
    
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Run the main async function
    asyncio.run(main())