/**
 * qma-mcp — stdio bridge between local MCP hosts (Claude Code, Cursor) and
 * the hosted QMA MCP server (Streamable HTTP).
 *
 * Env:
 *   QMA_MCP_URL    hosted MCP endpoint (default https://qma-api-7o9v.onrender.com/mcp)
 *   QMA_MCP_TOKEN  MCP connection token (OAuth scope "mcp", 30-day TTL)
 *
 * The token carries the owner's spend caps; every tools/call is re-validated
 * server-side, and revoking the connection on qma.market cuts access instantly.
 */
export declare function run(): Promise<void>;
