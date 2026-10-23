import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { ListToolsRequestSchema, CallToolRequestSchema } from '@modelcontextprotocol/sdk/types.js';
import { gmailDraftTool, handleGmailDraft } from './tools/gmailDraft.js';
import { googleDocsAppendTool, handleGoogleDocsAppend } from './tools/googleDocsAppend.js';
import { logger } from '../utils/logging.js';

// Reply Desk drafts, it never sends: there is deliberately no send tool here.
export const tools = [gmailDraftTool, googleDocsAppendTool];

export function setupMcpServer(): Server {
  const server = new Server(
    {
      name: 'reply-desk-mcp',
      version: '1.0.0',
    },
    {
      capabilities: {
        tools: {},
      },
    }
  );

  server.setRequestHandler(ListToolsRequestSchema, async () => {
    logger.debug('Handling ListToolsRequest');
    return {
      tools,
    };
  });

  server.setRequestHandler(CallToolRequestSchema, async (request) => {
    logger.info({ tool: request.params.name }, 'Handling CallToolRequest');

    switch (request.params.name) {
      case 'gmail_draft': {
        const response = await handleGmailDraft(request.params.arguments);
        return formatMcpResponse(response);
      }
      case 'google_docs_append': {
        const response = await handleGoogleDocsAppend(request.params.arguments);
        return formatMcpResponse(response);
      }
      default:
        throw new Error(`Unknown tool: ${request.params.name}`);
    }
  });

  return server;
}

function formatMcpResponse(response: any) {
  if (response.success) {
    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify(response, null, 2),
        },
      ],
    };
  } else {
    return {
      isError: true,
      content: [
        {
          type: 'text',
          text: JSON.stringify(response, null, 2),
        },
      ],
    };
  }
}
