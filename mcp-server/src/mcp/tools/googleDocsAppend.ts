import { GoogleDocsAppendSchema, GoogleDocsAppendInput } from '../../schemas/googleDocsSchemas.js';
import { googleDocsService } from '../../services/googleDocsService.js';
import { MCPToolResponse } from '../../types/common.js';
import { MCPToolError, ErrorCode } from '../../utils/errors.js';

export const googleDocsAppendTool = {
  name: 'google_docs_append',
  description: "Appends text content to the END of an existing Google Document. "
    + "Existing content is preserved. A newline separator is inserted before the appended text. "
    + "Requires the document ID (found in the Google Docs URL).",
  inputSchema: {
    type: "object",
    properties: {
      document_id: { type: "string", description: "The ID of the Google Document (found in URL)" },
      content: { type: "string", description: "The text content to append to the document" }
    },
    required: ["document_id", "content"]
  },
};

export async function handleGoogleDocsAppend(args: any): Promise<MCPToolResponse<any>> {
  try {
    const parsed = GoogleDocsAppendSchema.safeParse(args);
    if (!parsed.success) {
      return {
        success: false,
        error: {
          code: ErrorCode.MISSING_REQUIRED_FIELD,
          message: `Validation failed: ${parsed.error.message}`,
          retryable: false,
        },
      };
    }

    const result = await googleDocsService.appendContent(parsed.data);
    
    return {
      success: true,
      data: result,
      message: 'Content appended successfully',
    };
  } catch (error: any) {
    if (error instanceof MCPToolError) {
      return {
        success: false,
        error: {
          code: error.code,
          message: error.message,
          retryable: error.retryable,
        },
      };
    }
    return {
      success: false,
      error: {
        code: ErrorCode.INTERNAL_ERROR,
        message: 'An unexpected error occurred.',
        retryable: false,
      },
    };
  }
}
