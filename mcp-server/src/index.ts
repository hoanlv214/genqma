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

import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StreamableHTTPClientTransport } from "@modelcontextprotocol/sdk/client/streamableHttp.js";
import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";

const MCP_URL = process.env.QMA_MCP_URL || "https://qma-api-7o9v.onrender.com/mcp";
const MCP_TOKEN = process.env.QMA_MCP_TOKEN || "";

export async function run(): Promise<void> {
  if (!MCP_TOKEN) {
    console.error(
      "qma-mcp: QMA_MCP_TOKEN is required. Mint one via the QMA OAuth flow — see docs/mcp/quickstart-cli.md.",
    );
    process.exit(1);
  }

  const transport = new StreamableHTTPClientTransport(new URL(MCP_URL), {
    requestInit: { headers: { Authorization: `Bearer ${MCP_TOKEN}` } },
  });
  const upstream = new Client({ name: "qma-mcp-bridge", version: "0.1.0" });
  await upstream.connect(transport);

  const downstream = new Server(
    { name: "qma-mcp", version: "0.1.0" },
    { capabilities: { tools: {} } },
  );

  downstream.setRequestHandler(ListToolsRequestSchema, async () => {
    const listed = await upstream.listTools();
    return { tools: listed.tools };
  });

  downstream.setRequestHandler(CallToolRequestSchema, async (request) => {
    return upstream.callTool({
      name: request.params.name,
      arguments: request.params.arguments ?? {},
    });
  });

  const stdio = new StdioServerTransport();
  await downstream.connect(stdio);
  console.error(`qma-mcp: bridging stdio → ${MCP_URL}`);
}
