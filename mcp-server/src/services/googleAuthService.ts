import fs from 'fs/promises';
import { google } from 'googleapis';
import { OAuth2Client } from 'google-auth-library';
import { config } from '../config.js';
import { logger } from '../utils/logging.js';
import { MCPToolError, ErrorCode } from '../utils/errors.js';

export class GoogleAuthService {
  private oauth2Client: OAuth2Client;
  private isInitialized = false;

  constructor() {
    this.oauth2Client = new google.auth.OAuth2(
      config.google.clientId,
      config.google.clientSecret,
      config.google.redirectUri
    );

    this.oauth2Client.on('tokens', async (tokens) => {
      if (tokens.refresh_token) {
        logger.info('Received new refresh token.');
      }
      try {
        const currentTokens = await this.loadTokens();
        await this.saveTokens({ ...currentTokens, ...tokens });
      } catch (error) {
        logger.error({ error }, 'Failed to save updated tokens');
      }
    });
  }

  public async getAuthClient(): Promise<OAuth2Client> {
    if (!this.isInitialized) {
      await this.initialize();
    }
    return this.oauth2Client;
  }

  private async initialize() {
    try {
      const tokens = await this.loadTokens();
      if (tokens) {
        this.oauth2Client.setCredentials(tokens);
        this.isInitialized = true;
        logger.info('OAuth2 client initialized from stored tokens.');
      } else {
        throw new MCPToolError(
          ErrorCode.AUTHENTICATION_REQUIRED,
          'No stored credentials found. Please authenticate first.'
        );
      }
    } catch (error) {
      if (error instanceof MCPToolError) throw error;
      logger.error({ error }, 'Error initializing OAuth client');
      throw new MCPToolError(
        ErrorCode.AUTHENTICATION_FAILED,
        'Failed to initialize OAuth client.'
      );
    }
  }

  private async loadTokens(): Promise<any | null> {
    // Cloud: read from env var
    const envToken = process.env.GOOGLE_TOKEN_JSON;
    if (envToken) {
      try {
        return JSON.parse(envToken);
      } catch {
        logger.warn('GOOGLE_TOKEN_JSON env var is not valid JSON');
      }
    }

    // Local: read from file
    try {
      const data = await fs.readFile(config.google.tokenPath, 'utf8');
      return JSON.parse(data);
    } catch (error: any) {
      if (error.code === 'ENOENT') {
        return null;
      }
      throw error;
    }
  }

  private async saveTokens(tokens: any): Promise<void> {
    // Ensure data directory exists
    const dir = config.google.tokenPath.substring(0, config.google.tokenPath.lastIndexOf('/'));
    if (dir && dir !== '.') {
        await fs.mkdir(dir, { recursive: true });
    }
    await fs.writeFile(config.google.tokenPath, JSON.stringify(tokens, null, 2), 'utf8');
  }

  public getAuthUrl(): string {
    return this.oauth2Client.generateAuthUrl({
      access_type: 'offline',
      scope: config.google.scopes,
      prompt: 'consent', // Force consent to ensure we get a refresh token
    });
  }

  public async handleCallback(code: string): Promise<void> {
    const { tokens } = await this.oauth2Client.getToken(code);
    this.oauth2Client.setCredentials(tokens);
    await this.saveTokens(tokens);
    this.isInitialized = true;
    logger.info('Successfully authenticated and saved tokens.');
  }
}

export const authService = new GoogleAuthService();
