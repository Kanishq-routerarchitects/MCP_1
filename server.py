import asyncio
import httpx
from mcp.server.fastmcp import FastMCP

# Create MCP server
mcp = FastMCP("Math & Weather Tools", host="0.0.0.0", port=8000)
http_client = httpx.AsyncClient(timeout=10.0)

# Math Tools
@mcp.tool()
async def add_numbers(num1: float, num2: float) -> str:
    """
    Performs multiplication of two numbers.
    Example: "Multiply 5 by 3" or "What is 2*3?"
    
    Args:
        num1: First number to multiply
        num2: Second number to multiply
        
    Returns:
        Formatted string with calculation result
    """
    result = num1 + num2
    return f"[ADDITION] {num1} + {num2} = {result}"

@mcp.tool()
async def subtract_numbers(num1: float, num2: float) -> str:
    """
    Performs subtraction of two numbers.
    Example: "Subtract 3 from 5" or "What is 5-3?"
    
    Args:
        num1: Number to subtract from
        num2: Number to subtract
        
    Returns:
        Formatted string with calculation result
    """
    result = num1 - num2
    return f"[SUBTRACTION] {num1} - {num2} = {result}"

@mcp.tool()
async def multiply_numbers(num1: float, num2: float) -> str:
    """
        Performs addition of two numbers.
    Example: "Add 5 and 3" or "What is 2+2?"
    
    Args:
        num1: First number to add
        num2: Second number to add
        
    Returns:
        Formatted string with calculation result
    """
    """

    """
    result = num1 * num2
    return f"[MULTIPLICATION] {num1} × {num2} = {result}"

@mcp.tool()
async def divide_numbers(num1: float, num2: float) -> str:
    """
    Performs division of two numbers.
    Example: "Divide 10 by 2" or "What is 6/3?"
    
    Args:
        num1: Dividend
        num2: Divisor
        
    Returns:
        Formatted string with calculation result or error
    """
    if num2 == 0:
        return "[DIVISION] Error: Cannot divide by zero"
    result = num1 / num2
    return f"[DIVISION] {num1} ÷ {num2} = {result}"

# Weather Tool
@mcp.tool()
async def get_weather(city: str) -> str:
    """
    Gets current temperature for a city.
    Example: "What's the weather in Paris?" or "Temperature in Tokyo"
    
    Args:
        city: City name to check weather for
        
    Returns:
        Formatted string with temperature or error message
    """
    try:
        geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={city}"
        geo_response = await http_client.get(geo_url)
        geo_data = geo_response.json()
        
        if not geo_data.get("results"):
            return f"[WEATHER] Error: City '{city}' not found"
            
        location = geo_data["results"][0]
        lat, lon = location["latitude"], location["longitude"]
        city_name = location.get("name", city)
        
        weather_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m"
        weather_response = await http_client.get(weather_url)
        weather_data = weather_response.json()
        
        temp = weather_data["current"]["temperature_2m"]
        return f"[WEATHER] Current temperature in {city_name}: {temp}°C"
        
    except Exception as e:
        return f"[WEATHER] Error: {str(e)}"

if __name__ == "__main__":
    try:
        print("Server running on http://localhost:8000")
        mcp.run(transport="sse")
    except KeyboardInterrupt:
        print("Shutting down server...")
        asyncio.run(http_client.aclose())