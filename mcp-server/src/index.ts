import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { setupMcpServer } from './mcp/server.js';
import { authService } from './services/googleAuthService.js';
import { logger } from './utils/logging.js';

async function main() {
  logger.info('Starting the Reply Desk MCP server (Docs append, Gmail draft; no send)');
  
  try {
    // Attempt to initialize auth (this will read the stored tokens if they exist)
    try {
      await authService.getAuthClient();
      logger.info('Authentication successful.');
    } catch (authError: any) {
      logger.error('Authentication required. Please authenticate before using the server tools.');
      logger.info(`OAuth URL: ${authService.getAuthUrl()}`);
      logger.info('Run the auth script or open this URL to get a code.');
    }

    const server = setupMcpServer();
    const transport = new StdioServerTransport();
    
    await server.connect(transport);
    logger.info('MCP Server connected via STDIO transport.');
    
  } catch (error) {
    logger.error({ error }, 'Failed to start MCP server');
    process.exit(1);
  }
}

main();
