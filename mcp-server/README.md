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
5. Put `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, and `REPLY_DESK_DOC_ID` in the root `.env`, then sign in:

   ```bash
   make install        # builds mcp-server/dist
   make google-auth    # opens Google's consent page; saves mcp-server/data/google-token.json
   ```

   The sign-in redirects to a one-time listener on `http://127.0.0.1:8765/`, so no code is pasted anywhere. The token file is gitignored and readable by you only. (`npm run auth` in this folder still works, with a copy-and-paste code.)

## Turning it on

Locally, set `REPLY_DESK_MCP=on` in the root `.env`. On Render, save a Render API key to `~/.render-api-key` (`chmod 600`) and run:

```bash
make render-env                     # sets the five variables below on reply-desk-api and redeploys
make render-env SAVE_ACCESS_CODE=1  # also saves the API's ACCESS_CODE to ~/.reply-desk-access-code
```

| Variable | Value |
|---|---|
| `REPLY_DESK_MCP` | `on` |
| `REPLY_DESK_DOC_ID` | the Doc id from step 4 |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` | from step 3 |
| `GOOGLE_TOKEN_JSON` | Render only: the contents of `mcp-server/data/google-token.json` |

`make render-env` checks the token with Google before sending it, sets each variable on its own (every other variable stays as it is), and prints names only. `/api/health` then reports `"mcp": {"enabled": true, "doc_configured": true}`. After each approve, the approved note shows whether the Doc append and the Gmail draft were done; a failure shows the server's error code and never undoes the approval.

## Renewing the token (Testing mode)

While the Google app is in Testing mode, the refresh token lasts 7 days. When the approved note shows `AUTHENTICATION_FAILED`, or before the date `make google-auth` printed:

```bash
make google-auth && make render-env
```

Publishing the app (Google Auth Platform → Audience → Publish app) removes the 7-day limit.

## Development

```bash
npm test        # schema and tool-list tests
npm run build   # dist/, which the API runs
```

The Python tests (`tests/test_workspace.py`) include a real stdio round trip against `dist/` with placeholder OAuth settings. It stops at the auth check, so nothing reaches Google.
