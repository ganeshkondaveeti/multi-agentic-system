import { ErrorCode } from '../utils/errors.js';

export interface BaseResponse {
  success: boolean;
  message?: string;
}

export interface SuccessResponse<T> extends BaseResponse {
  success: true;
  data: T;
}

export interface ErrorResponse extends BaseResponse {
  success: false;
  error: {
    code: ErrorCode | string;
    message: string;
    retryable: boolean;
  };
}

export type MCPToolResponse<T> = SuccessResponse<T> | ErrorResponse;
