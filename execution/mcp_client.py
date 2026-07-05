import asyncio
import sys
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.client.session import ClientSession

async def _call_tool_async(server_script_path: str, tool_name: str, tool_args: dict) -> str:
    """
    Asynchronous internal function to call an MCP tool over stdio.
    """
    server_params = StdioServerParameters(
        command=sys.executable,
        args=[server_script_path]
    )
    
    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                
                result = await session.call_tool(tool_name, arguments=tool_args)
                
                # result.content is usually a list of TextContent or ImageContent
                if result.isError:
                    return f"Error from MCP server: {result.content}"
                
                # Simple extraction of text content
                texts = [c.text for c in result.content if getattr(c, "type", "") == "text"]
                return "\n".join(texts) if texts else str(result.content)
                
    except Exception as e:
        return f"Error communicating with MCP server {server_script_path}: {e}"

def call_mcp_tool(server_script_path: str, tool_name: str, tool_args: dict) -> str:
    """
    Deterministic function to invoke a tool on a local MCP server over stdio.
    This acts as the MCP client layer.
    """
    return asyncio.run(_call_tool_async(server_script_path, tool_name, tool_args))
