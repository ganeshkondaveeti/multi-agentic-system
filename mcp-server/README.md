# Reply Desk MCP server

The approval-gated MCP step from the problem statement. After a human clicks **Approve**, the API (`support_reply.workspace`) starts this server as a stdio subprocess and calls two tools:

- `google_docs_append`: appends the redacted record as one line to a Google Doc.
- `gmail_draft`: creates a Gmail draft of the reply with no recipient. Whoever sends it from Gmail adds the customer's address, which the app never stores.

There is no send tool. The server came from the Milestone 2 MCP server, without its `gmail_send` tool and its unauthenticated HTTP transport. It logs to stderr, because stdout carries the MCP protocol.

## One-time Google setup

1. In the [Google Cloud Console](https://console.cloud.google.com/), create a project and enable the **Gmail API** and the **Google Docs API**.
2. Configure the OAuth consent screen and add the scopes `https://www.googleapis.com/auth/gmail.compose` and `https://www.googleapis.com/auth/documents`. While the app is in **Testing**, add your Google account as a test user. Google expires refresh tokens for Testing apps after 7 days, so publish the app, or repeat step 5 when drafts start failing with `AUTHENTICATION_FAILED`.
3. Create an **OAuth client ID** of type **Desktop app** and note its client ID and secret.
4. Create a Google Doc for the records. Its id is the part of the URL between `/d/` and `/edit`.
5. Get a token:

   ```bash
   cd mcp-server
   npm ci && npm run build
   GOOGLE_CLIENT_ID=… GOOGLE_CLIENT_SECRET=… GOOGLE_REDIRECT_URI=http://localhost:3000/oauth/callback npm run auth
   ```

   Open the URL it prints, approve, and paste the code back. The token is saved to `mcp-server/data/google-token.json`, which is gitignored.

## Turning it on

In the root `.env` (local) or the API's Render environment:

| Variable | Value |
|---|---|
| `REPLY_DESK_MCP` | `on` |
| `REPLY_DESK_DOC_ID` | the Doc id from step 4 |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` | from step 3 |
| `GOOGLE_TOKEN_JSON` | Render only: the contents of `mcp-server/data/google-token.json` |

`/api/health` then reports `"mcp": {"enabled": true, "doc_configured": true}`. After each approve, the approved note shows whether the Doc append and the Gmail draft were done; a failure shows the server's error code and never undoes the approval.

## Development

```bash
npm test        # schema and tool-list tests
npm run build   # dist/, which the API runs
```

The Python tests (`tests/test_workspace.py`) include a real stdio round trip against `dist/` with placeholder OAuth settings. It stops at the auth check, so nothing reaches Google.
