import { describe, it, expect } from 'vitest';

// config.ts exits when the OAuth client settings are missing, so set placeholders
// before the server module is loaded. Nothing here calls Google.
process.env.GOOGLE_CLIENT_ID ??= 'test-client-id';
process.env.GOOGLE_CLIENT_SECRET ??= 'test-client-secret';
process.env.GOOGLE_REDIRECT_URI ??= 'http://localhost:3000/oauth/callback';

// The first import loads googleapis, which can take several seconds on a cold cache.
describe('MCP tools', { timeout: 30_000 }, () => {
  it('offers drafting and appending, and no way to send', async () => {
    const { tools } = await import('../src/mcp/server.js');
    const names = tools.map((tool) => tool.name).sort();
    expect(names).toEqual(['gmail_draft', 'google_docs_append']);
    expect(names.some((name) => name.includes('send'))).toBe(false);
  });

  it('does not require a recipient on a draft', async () => {
    const { tools } = await import('../src/mcp/server.js');
    const draft = tools.find((tool) => tool.name === 'gmail_draft')!;
    expect(draft.inputSchema.required).toEqual(['subject', 'body']);
  });
});
