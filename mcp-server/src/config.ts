import dotenv from 'dotenv';
import { z } from 'zod';

// Load environment variables from .env file. Quiet: under the stdio transport, stdout
// carries the MCP protocol, so nothing else may print there.
dotenv.config({ quiet: true });

const configSchema = z.object({
  GOOGLE_CLIENT_ID: z.string().min(1, "GOOGLE_CLIENT_ID is required"),
  GOOGLE_CLIENT_SECRET: z.string().min(1, "GOOGLE_CLIENT_SECRET is required"),
  GOOGLE_REDIRECT_URI: z.string().min(1, "GOOGLE_REDIRECT_URI is required"),
  GOOGLE_TOKEN_PATH: z.string().default('./data/google-token.json'),
  GOOGLE_TOKEN_JSON: z.string().optional(),
  PORT: z.string().default('3000'),
  LOG_LEVEL: z.enum(['debug', 'info', 'warn', 'error']).default('info'),
  NODE_ENV: z.enum(['development', 'production', 'test']).default('development'),
});

const parsedConfig = configSchema.safeParse(process.env);

if (!parsedConfig.success) {
  console.error('Invalid environment variables:', JSON.stringify(parsedConfig.error.format(), null, 2));
  process.exit(1);
}

export const config = {
  google: {
    clientId: parsedConfig.data.GOOGLE_CLIENT_ID,
    clientSecret: parsedConfig.data.GOOGLE_CLIENT_SECRET,
    redirectUri: parsedConfig.data.GOOGLE_REDIRECT_URI,
    tokenPath: parsedConfig.data.GOOGLE_TOKEN_PATH,
    scopes: [
      'https://www.googleapis.com/auth/gmail.compose',
      'https://www.googleapis.com/auth/documents',
    ],
  },
  logging: {
    level: parsedConfig.data.LOG_LEVEL,
  },
  nodeEnv: parsedConfig.data.NODE_ENV,
};
