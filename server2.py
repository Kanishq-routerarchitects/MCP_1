#!/usr/bin/env python3

import asyncio
import json
import math
import os
import random
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, AsyncGenerator
from contextlib import asynccontextmanager

import pyodbc
from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

# Global database connection
db_connection = None

# Store active SSE connections
active_connections: Dict[str, asyncio.Queue] = {}

# MCP Protocol Models
class MCPRequest(BaseModel):
    jsonrpc: str = "2.0"
    id: Optional[int] = None
    method: str
    params: Dict[str, Any] = {}

class MCPResponse(BaseModel):
    jsonrpc: str = "2.0"
    id: Optional[int] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None

class MCPNotification(BaseModel):
    jsonrpc: str = "2.0"
    method: str
    params: Dict[str, Any] = {}

# FastAPI lifespan context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan context manager"""
    print("🚀 Starting FastMCP SSE Server...")
    print("📋 Available Tools:")
    print("   API Tools (Priority 1):")
    print("   • calculator - Mathematical calculations")
    print("   • weather_info - Weather information")
    print("   • currency_converter - Currency conversion")
    print("   • time_info - Time and date information")
    print("   • text_analyzer - Text analysis")
    print("   Database Tools (Priority 2):")
    print("   • list_tables - List all database tables")
    print("   • describe_table - Describe table structure")
    print("   • execute_query - Execute SQL queries")
    print("   • count_records - Count table records")
    print("   • table_sample - Get sample table data")
    print("🌐 Server running on HTTP with SSE transport...")
    
    # Initialize database connection
    try:
        await get_db_connection()
    except Exception as e:
        print(f"⚠️ Database connection failed: {e}")
        print("🚀 Server will continue with API tools only")
    
    yield
    
    print("🛑 Shutting down FastMCP SSE Server...")
    # Cleanup database connection
    global db_connection
    if db_connection:
        try:
            db_connection.close()
        except:
            pass
    print("✅ Server shutdown complete")

# Initialize FastAPI app
app = FastAPI(
    title="FastMCP SSE Server",
    description="Hybrid API-Database MCP Server with Server-Sent Events",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

async def get_db_connection():
    """Get database connection with configuration from environment"""
    global db_connection
    if db_connection is None:
        try:
            server = os.getenv("MSSQL_SERVER", "localhost")
            database = os.getenv("MSSQL_DATABASE", "testdb")
            username = os.getenv("MSSQL_USER", "sa")
            password = os.getenv("MSSQL_PASSWORD", "password")
            port = os.getenv("MSSQL_PORT", "1433")
            
            connection_string = (
                f"DRIVER={{ODBC Driver 17 for SQL Server}};"
                f"SERVER={server},{port};"
                f"DATABASE={database};"
                f"UID={username};"
                f"PWD={password};"
                f"TrustServerCertificate=yes;"
                f"Encrypt=yes;"
                f"Connection Timeout=30;"
            )
            
            db_connection = pyodbc.connect(connection_string)
            print(f"✅ Database connected: {server}:{port}/{database}")
        except Exception as e:
            print(f"❌ Database connection failed: {str(e)}")
            print("🚀 Continuing with API tools only")
            db_connection = None
    return db_connection

# =============================================================================
# API TOOLS (Priority 1 - Try these first)
# =============================================================================

async def calculator(expression: str) -> str:
    """Calculate mathematical expressions safely."""
    try:
        # Clean the expression
        expression = expression.strip()
        if not expression:
            return "Error: Empty expression provided"
        
        # Remove question marks and other non-math characters
        expression = expression.replace('?', '').replace('=', '').strip()
        
        allowed_names = {
            k: v for k, v in math.__dict__.items() 
            if not k.startswith("__")
        }
        allowed_names.update({
            "abs": abs, "round": round, "min": min, "max": max,
            "sum": sum, "pow": pow
        })
        
        # Remove dangerous functions
        for dangerous in ["__import__", "eval", "exec", "open", "input"]:
            allowed_names.pop(dangerous, None)
        
        result = eval(expression, {"__builtins__": {}}, allowed_names)
        return f"Result: {result}"
    except Exception as e:
        return f"Error calculating '{expression}': {str(e)}"

async def weather_info(city: str) -> str:
    """Get current weather information for a city."""
    try:
        weather_data = {
            "mumbai": {"temp": 32, "condition": "Humid", "humidity": 85},
            "delhi": {"temp": 35, "condition": "Hot", "humidity": 60},
            "bangalore": {"temp": 25, "condition": "Pleasant", "humidity": 70},
            "chennai": {"temp": 30, "condition": "Sunny", "humidity": 80},
            "kolkata": {"temp": 28, "condition": "Cloudy", "humidity": 75},
        }
        
        city_lower = city.lower()
        if city_lower in weather_data:
            data = weather_data[city_lower]
            return (f"Weather in {city.title()}:\n"
                   f"Temperature: {data['temp']}°C\n"
                   f"Condition: {data['condition']}\n"
                   f"Humidity: {data['humidity']}%")
        else:
            temp = random.randint(15, 40)
            conditions = ["Sunny", "Cloudy", "Rainy", "Partly Cloudy"]
            humidity = random.randint(40, 90)
            return (f"Weather in {city.title()}:\n"
                   f"Temperature: {temp}°C\n"
                   f"Condition: {random.choice(conditions)}\n"
                   f"Humidity: {humidity}%")
    except Exception as e:
        return f"Error fetching weather for {city}: {str(e)}"

async def currency_converter(amount: float, from_currency: str, to_currency: str) -> str:
    """Convert currency from one type to another."""
    try:
        exchange_rates = {
            "USD": {"INR": 83.0, "EUR": 0.85, "GBP": 0.73},
            "EUR": {"INR": 97.6, "USD": 1.18, "GBP": 0.86},
            "INR": {"USD": 0.012, "EUR": 0.010, "GBP": 0.009},
            "GBP": {"USD": 1.37, "EUR": 1.16, "INR": 113.9}
        }
        
        from_curr = from_currency.upper()
        to_curr = to_currency.upper()
        
        if from_curr == to_curr:
            return f"{amount} {from_curr} = {amount} {to_curr}"
        
        if from_curr in exchange_rates and to_curr in exchange_rates[from_curr]:
            rate = exchange_rates[from_curr][to_curr]
            converted = amount * rate
            return (f"{amount} {from_curr} = {converted:.2f} {to_curr}\n"
                   f"Exchange rate: 1 {from_curr} = {rate} {to_curr}")
        else:
            return f"Exchange rate not available for {from_curr} to {to_curr}"
    except Exception as e:
        return f"Error converting currency: {str(e)}"

async def time_info(timezone: str = "UTC") -> str:
    """Get current time information."""
    try:
        current_time = datetime.now()
        return (f"Current Time Information:\n"
               f"DateTime: {current_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
               f"Day: {current_time.strftime('%A')}\n"
               f"Timezone: {timezone}\n"
               f"Timestamp: {current_time.timestamp()}")
    except Exception as e:
        return f"Error getting time info: {str(e)}"

async def text_analyzer(text: str) -> str:
    """Analyze text and provide statistics."""
    try:
        words = text.split()
        sentences = text.split('.')
        paragraphs = text.split('\n\n')
        
        return (f"Text Analysis:\n"
               f"Characters: {len(text)}\n"
               f"Words: {len(words)}\n"
               f"Sentences: {len([s for s in sentences if s.strip()])}\n"
               f"Paragraphs: {len([p for p in paragraphs if p.strip()])}\n"
               f"Average words per sentence: {len(words) / max(len(sentences), 1):.1f}")
    except Exception as e:
        return f"Error analyzing text: {str(e)}"

# =============================================================================
# DATABASE TOOLS (Priority 2 - Fallback when API tools don't match)
# =============================================================================

async def list_tables() -> str:
    """List all tables in the database."""
    try:
        conn = await get_db_connection()
        if not conn:
            return "❌ Database connection not available"
        
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT TABLE_NAME 
            FROM INFORMATION_SCHEMA.TABLES 
            WHERE TABLE_TYPE = 'BASE TABLE'
            ORDER BY TABLE_NAME
        """)
        
        tables = [row[0] for row in cursor.fetchall()]
        cursor.close()
        
        if tables:
            return "Available Tables:\n" + "\n".join(f"• {table}" for table in tables)
        else:
            return "No tables found in the database."
    except Exception as e:
        return f"Error listing tables: {str(e)}"

async def describe_table(table_name: str) -> str:
    """Describe the structure of a database table."""
    try:
        conn = await get_db_connection()
        if not conn:
            return "❌ Database connection not available"
        
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                COLUMN_NAME,
                DATA_TYPE,
                IS_NULLABLE,
                COLUMN_DEFAULT,
                CHARACTER_MAXIMUM_LENGTH
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_NAME = ?
            ORDER BY ORDINAL_POSITION
        """, (table_name,))
        
        columns = cursor.fetchall()
        cursor.close()
        
        if not columns:
            return f"Table '{table_name}' not found."
        
        result = f"Table Structure: {table_name}\n" + "="*50 + "\n"
        for col in columns:
            col_name, data_type, nullable, default, max_length = col
            length_info = f"({max_length})" if max_length else ""
            nullable_info = "NULL" if nullable == "YES" else "NOT NULL"
            default_info = f"DEFAULT {default}" if default else ""
            
            result += f"{col_name:<20} {data_type}{length_info:<15} {nullable_info:<10} {default_info}\n"
        
        return result
    except Exception as e:
        return f"Error describing table '{table_name}': {str(e)}"

async def execute_query(query: str, limit: int = 100) -> str:
    """Execute a SQL query and return results."""
    try:
        conn = await get_db_connection()
        if not conn:
            return "❌ Database connection not available"
        
        cursor = conn.cursor()
        
        query_upper = query.upper().strip()
        if query_upper.startswith('SELECT') and 'LIMIT' not in query_upper and 'TOP' not in query_upper:
            query = query.replace('SELECT', f'SELECT TOP {limit}', 1)
        
        cursor.execute(query)
        
        if query_upper.startswith('SELECT'):
            columns = [description[0] for description in cursor.description]
            rows = cursor.fetchall()
            
            if not rows:
                return "Query executed successfully. No results returned."
            
            result = "Query Results:\n" + "="*50 + "\n"
            result += " | ".join(f"{col:<15}" for col in columns) + "\n"
            result += "-"*50 + "\n"
            
            for row in rows:
                result += " | ".join(f"{str(val):<15}" for val in row) + "\n"
            
            result += f"\nTotal rows: {len(rows)}"
            if len(rows) == limit:
                result += f" (Limited to {limit} rows)"
            
            return result
        else:
            conn.commit()
            return "Query executed successfully."
    
    except Exception as e:
        return f"Error executing query: {str(e)}"
    finally:
        if 'cursor' in locals():
            cursor.close()

async def count_records(table_name: str, where_clause: str = "") -> str:
    """Count records in a table with optional WHERE clause."""
    try:
        conn = await get_db_connection()
        if not conn:
            return "❌ Database connection not available"
        
        query = f"SELECT COUNT(*) FROM {table_name}"
        if where_clause:
            query += f" WHERE {where_clause}"
        
        cursor = conn.cursor()
        cursor.execute(query)
        count = cursor.fetchone()[0]
        cursor.close()
        
        where_info = f" (WHERE {where_clause})" if where_clause else ""
        return f"Table '{table_name}'{where_info}: {count:,} records"
    except Exception as e:
        return f"Error counting records in '{table_name}': {str(e)}"

async def table_sample(table_name: str, sample_size: int = 5) -> str:
    """Get a sample of records from a table."""
    try:
        conn = await get_db_connection()
        if not conn:
            return "❌ Database connection not available"
        
        query = f"SELECT TOP {sample_size} * FROM {table_name}"
        return await execute_query(query, sample_size)
    except Exception as e:
        return f"Error sampling table '{table_name}': {str(e)}"

# =============================================================================
# TOOL REGISTRY
# =============================================================================

TOOLS = {
    "calculator": {
        "name": "calculator",
        "description": "Calculate mathematical expressions safely",
        "inputSchema": {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "Mathematical expression to calculate"
                }
            },
            "required": ["expression"]
        },
        "handler": calculator
    },
    "weather_info": {
        "name": "weather_info",
        "description": "Get current weather information for a city",
        "inputSchema": {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "Name of the city"
                }
            },
            "required": ["city"]
        },
        "handler": weather_info
    },
    "currency_converter": {
        "name": "currency_converter",
        "description": "Convert currency from one type to another",
        "inputSchema": {
            "type": "object",
            "properties": {
                "amount": {"type": "number", "description": "Amount to convert"},
                "from_currency": {"type": "string", "description": "Source currency code"},
                "to_currency": {"type": "string", "description": "Target currency code"}
            },
            "required": ["amount", "from_currency", "to_currency"]
        },
        "handler": currency_converter
    },
    "time_info": {
        "name": "time_info",
        "description": "Get current time information",
        "inputSchema": {
            "type": "object",
            "properties": {
                "timezone": {"type": "string", "description": "Timezone", "default": "UTC"}
            }
        },
        "handler": time_info
    },
    "text_analyzer": {
        "name": "text_analyzer",
        "description": "Analyze text and provide statistics",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Text to analyze"}
            },
            "required": ["text"]
        },
        "handler": text_analyzer
    },
    "list_tables": {
        "name": "list_tables",
        "description": "List all tables in the database",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": list_tables
    },
    "describe_table": {
        "name": "describe_table",
        "description": "Describe the structure of a database table",
        "inputSchema": {
            "type": "object",
            "properties": {
                "table_name": {"type": "string", "description": "Name of the table"}
            },
            "required": ["table_name"]
        },
        "handler": describe_table
    },
    "execute_query": {
        "name": "execute_query",
        "description": "Execute a SQL query and return results",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "SQL query to execute"},
                "limit": {"type": "integer", "description": "Max rows to return", "default": 100}
            },
            "required": ["query"]
        },
        "handler": execute_query
    },
    "count_records": {
        "name": "count_records",
        "description": "Count records in a table",
        "inputSchema": {
            "type": "object",
            "properties": {
                "table_name": {"type": "string", "description": "Name of the table"},
                "where_clause": {"type": "string", "description": "Optional WHERE clause"}
            },
            "required": ["table_name"]
        },
        "handler": count_records
    },
    "table_sample": {
        "name": "table_sample",
        "description": "Get a sample of records from a table",
        "inputSchema": {
            "type": "object",
            "properties": {
                "table_name": {"type": "string", "description": "Name of the table"},
                "sample_size": {"type": "integer", "description": "Number of sample records", "default": 5}
            },
            "required": ["table_name"]
        },
        "handler": table_sample
    }
}

# =============================================================================
# MCP PROTOCOL HANDLERS
# =============================================================================

async def handle_initialize(params: Dict[str, Any]) -> Dict[str, Any]:
    """Handle MCP initialize request"""
    return {
        "protocolVersion": "2024-11-05",
        "capabilities": {
            "tools": {"listChanged": True},
            "resources": {"subscribe": True, "listChanged": True}
        },
        "serverInfo": {
            "name": "FastMCP SSE Server",
            "version": "1.0.0"
        }
    }

async def handle_tools_list() -> Dict[str, Any]:
    """Handle tools/list request"""
    tools = []
    for tool_name, tool_info in TOOLS.items():
        tools.append({
            "name": tool_info["name"],
            "description": tool_info["description"],
            "inputSchema": tool_info["inputSchema"]
        })
    
    return {"tools": tools}

async def handle_tools_call(name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Handle tools/call request"""
    if name not in TOOLS:
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"❌ Tool '{name}' not found"
                }
            ]
        }
    
    tool = TOOLS[name]
    handler = tool["handler"]
    
    try:
        # Call the tool handler
        if asyncio.iscoroutinefunction(handler):
            result = await handler(**arguments)
        else:
            result = handler(**arguments)
        
        return {
            "content": [
                {
                    "type": "text",
                    "text": result
                }
            ]
        }
    except Exception as e:
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"❌ Error executing tool '{name}': {str(e)}"
                }
            ]
        }

# =============================================================================
# HTTP ENDPOINTS
# =============================================================================

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "FastMCP SSE Server is running",
        "version": "1.0.0",
        "status": "healthy",
        "endpoints": {
            "mcp": "/mcp",
            "events": "/events/{connection_id}",
            "tools": "/tools"
        }
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "database": "connected" if db_connection else "disconnected",
        "tools": len(TOOLS)
    }

@app.get("/tools")
async def get_tools():
    """Get available tools"""
    return await handle_tools_list()

@app.post("/mcp")
async def handle_mcp_request(request: MCPRequest):
    """Handle MCP protocol requests"""
    try:
        if request.method == "initialize":
            result = await handle_initialize(request.params)
            return MCPResponse(id=request.id, result=result)
        
        elif request.method == "tools/list":
            result = await handle_tools_list()
            return MCPResponse(id=request.id, result=result)
        
        elif request.method == "tools/call":
            name = request.params.get("name")
            arguments = request.params.get("arguments", {})
            result = await handle_tools_call(name, arguments)
            return MCPResponse(id=request.id, result=result)
        
        else:
            return MCPResponse(
                id=request.id,
                error={"code": -32601, "message": f"Method '{request.method}' not found"}
            )
    
    except Exception as e:
        return MCPResponse(
            id=request.id,
            error={"code": -32603, "message": f"Internal error: {str(e)}"}
        )

@app.get("/events/{connection_id}")
async def sse_endpoint(connection_id: str):
    """Server-Sent Events endpoint"""
    
    async def event_generator() -> AsyncGenerator[str, None]:
        # Create a queue for this connection
        queue = asyncio.Queue()
        active_connections[connection_id] = queue
        
        try:
            yield f"data: {json.dumps({'type': 'connected', 'connectionId': connection_id})}\n\n"
            
            while True:
                try:
                    # Wait for messages with timeout
                    message = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield f"data: {json.dumps(message)}\n\n"
                except asyncio.TimeoutError:
                    # Send keepalive
                    yield f"data: {json.dumps({'type': 'keepalive', 'timestamp': datetime.now().isoformat()})}\n\n"
                
        except asyncio.CancelledError:
            pass
        finally:
            # Clean up connection
            active_connections.pop(connection_id, None)
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Cache-Control"
        }
    )

@app.post("/events/{connection_id}/send")
async def send_event(connection_id: str, event: Dict[str, Any]):
    """Send event to specific SSE connection"""
    if connection_id in active_connections:
        await active_connections[connection_id].put(event)
        return {"status": "sent"}
    else:
        raise HTTPException(status_code=404, detail="Connection not found")

@app.get("/connections")
async def get_connections():
    """Get active SSE connections"""
    return {
        "active_connections": list(active_connections.keys()),
        "count": len(active_connections)
    }

# =============================================================================
# SERVER STARTUP
# =============================================================================

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "0.0.0.0")
    
    print(f"🚀 Starting FastMCP SSE Server on {host}:{port}")
    
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info",
        access_log=True
    )