import { authService } from '../services/googleAuthService.js';
import * as readline from 'readline/promises';
import { stdin as input, stdout as output } from 'process';
import { logger } from '../utils/logging.js';

async function main() {
  const url = authService.getAuthUrl();
  console.log('\n=============================================');
  console.log('Authorize this app by visiting this url:');
  console.log(url);
  console.log('=============================================\n');
  
  const rl = readline.createInterface({ input, output });
  const code = await rl.question('Enter the code from that page here: ');
  
  try {
    await authService.handleCallback(code.trim());
    console.log('\nToken stored successfully! You can now start the MCP server.');
  } catch (error) {
    console.error('\nError storing token:', error);
  } finally {
    rl.close();
  }
}

main();
