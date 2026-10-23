import { google, gmail_v1 } from 'googleapis';
import { authService } from './googleAuthService.js';
import { GmailDraftInput } from '../schemas/gmailSchemas.js';
import { MCPToolError, ErrorCode } from '../utils/errors.js';
import { logger } from '../utils/logging.js';

export class GmailService {
  private async getGmailApi(): Promise<gmail_v1.Gmail> {
    try {
      const auth = await authService.getAuthClient();
      return google.gmail({ version: 'v1', auth });
    } catch (error: any) {
       if (error instanceof MCPToolError) throw error;
       throw new MCPToolError(ErrorCode.AUTHENTICATION_FAILED, 'Failed to authenticate with Gmail API');
    }
  }

  private constructMimeMessage(input: GmailDraftInput): string {
    const lines = [];
    if (input.to.length > 0) {
      lines.push(`To: ${input.to.join(', ')}`);
    }
    if (input.cc && input.cc.length > 0) {
      lines.push(`Cc: ${input.cc.join(', ')}`);
    }
    if (input.bcc && input.bcc.length > 0) {
      lines.push(`Bcc: ${input.bcc.join(', ')}`);
    }
    lines.push(`Subject: ${input.subject}`);
    lines.push('Content-Type: text/plain; charset="UTF-8"');
    lines.push('');
    lines.push(input.body);

    const message = lines.join('\r\n');
    return Buffer.from(message).toString('base64url');
  }

  public async createDraft(input: GmailDraftInput) {
    try {
      const gmail = await this.getGmailApi();
      const raw = this.constructMimeMessage(input);

      logger.info({ subject: input.subject }, 'Creating Gmail draft');
      const response = await gmail.users.drafts.create({
        userId: 'me',
        requestBody: {
          message: { raw },
        },
      });

      return {
        draftId: response.data.id,
        messageId: response.data.message?.id,
      };
    } catch (error: any) {
      if (error instanceof MCPToolError) throw error;
      this.handleApiError(error, 'draft creation');
    }
  }

  private handleApiError(error: any, operation: string): never {
    // Status only: a Google API error carries the request, and so the draft body.
    logger.error({ status: error.response?.status }, `Error during ${operation}`);
    
    if (error.response) {
      const status = error.response.status;
      if (status === 401 || status === 403) {
        throw new MCPToolError(ErrorCode.INSUFFICIENT_PERMISSIONS, `Insufficient permissions for ${operation}. Check OAuth scopes.`, false);
      }
      if (status === 429) {
        throw new MCPToolError(ErrorCode.RATE_LIMITED, `Rate limited by Gmail API during ${operation}.`, true);
      }
      throw new MCPToolError(ErrorCode.GMAIL_API_ERROR, `Gmail API error during ${operation}: ${error.message}`, false);
    }
    
    throw new MCPToolError(ErrorCode.INTERNAL_ERROR, `Unexpected error during ${operation}`, false);
  }
}

export const gmailService = new GmailService();
