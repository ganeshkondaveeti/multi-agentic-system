import { describe, it, expect } from 'vitest';
import { GmailDraftInputSchema } from '../src/schemas/gmailSchemas.js';
import { GoogleDocsAppendSchema } from '../src/schemas/googleDocsSchemas.js';

describe('Gmail draft schema', () => {
  it('accepts a draft with recipients', () => {
    const result = GmailDraftInputSchema.safeParse({ to: ['test@example.com'], subject: 'Hello', body: 'World' });
    expect(result.success).toBe(true);
  });

  it('accepts a draft without recipients, for a person to address in Gmail', () => {
    const result = GmailDraftInputSchema.safeParse({ subject: 'Hello', body: 'World' });
    expect(result.success).toBe(true);
    expect(result.data?.to).toEqual([]);
  });

  it('rejects a draft without a subject', () => {
    expect(GmailDraftInputSchema.safeParse({ to: ['test@example.com'], body: 'World' }).success).toBe(false);
  });

  it('rejects a malformed recipient', () => {
    expect(GmailDraftInputSchema.safeParse({ to: ['not-an-email'], subject: 'Hello', body: 'World' }).success).toBe(false);
  });
});

describe('Google Docs append schema', () => {
  it('accepts a document id and content', () => {
    expect(GoogleDocsAppendSchema.safeParse({ document_id: '1234567890abcdef', content: 'New line' }).success).toBe(true);
  });

  it('rejects an append without content', () => {
    expect(GoogleDocsAppendSchema.safeParse({ document_id: '1234567890abcdef' }).success).toBe(false);
  });
});
