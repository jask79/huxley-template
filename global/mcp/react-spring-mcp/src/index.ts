#!/usr/bin/env node
import { Server } from "@modelcontextprotocol/sdk/server/index.js"
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js"
import {
  ListToolsRequestSchema,
  CallToolRequestSchema
} from "@modelcontextprotocol/sdk/types.js"
import { DataLoader } from "./data-loader.js"
import { getHookApi } from "./tools/hook-api.js"
import { getConcept } from "./tools/concept.js"
import { listDocumentation } from "./tools/list-documentation.js"

const server = new Server(
  {
    name: "react-spring-mcp",
    version: "1.1.0"
  },
  {
    capabilities: {
      tools: {}
    }
  }
)

const dataLoader = new DataLoader()

// List available tools
server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: [
    {
      name: "list_documentation",
      description: "List all available hooks and concepts with brief descriptions. Use this to discover what documentation is available.",
      inputSchema: {
        type: "object",
        properties: {
          category: {
            type: "string",
            enum: ["hooks", "concepts", "all"],
            description: "Category to list: 'hooks' for animation hooks, 'concepts' for conceptual guides, 'all' for everything (default: 'all')",
            default: "all"
          }
        }
      }
    },
    {
      name: "get_hook_api",
      description: "Get react-spring hook API documentation with examples, physics explanations, and usage patterns",
      inputSchema: {
        type: "object",
        properties: {
          hook: {
            type: "string",
            description: "Hook name (e.g., 'useSpring', 'useTrail', 'useTransition', 'useSpringRef', 'config')"
          }
        },
        required: ["hook"]
      }
    },
    {
      name: "get_concept",
      description: "Get react-spring conceptual documentation about animation principles, physics, and best practices",
      inputSchema: {
        type: "object",
        properties: {
          concept: {
            type: "string",
            description: "Concept name (e.g., 'spring-physics' for understanding spring physics and tuning)"
          }
        },
        required: ["concept"]
      }
    }
  ]
}))

// Handle tool calls
server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params

  switch (name) {
    case "list_documentation":
      return listDocumentation(
        dataLoader,
        (args as any)?.category as 'hooks' | 'concepts' | 'all' | undefined
      )

    case "get_hook_api":
      return getHookApi(dataLoader, (args as any).hook as string)

    case "get_concept":
      return getConcept(dataLoader, (args as any).concept as string)

    default:
      return {
        content: [{
          type: "text",
          text: `Unknown tool: ${name}`
        }],
        isError: true
      }
  }
})

// Start server
async function main() {
  const transport = new StdioServerTransport()
  await server.connect(transport)

  // Warm cache on startup
  await dataLoader.warmCache()

  console.error("React-Spring MCP server running")
}

main().catch(console.error)
