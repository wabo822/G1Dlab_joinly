# Joinly MCP

Endpoint: `https://isep.wangjiahan.com/mcp`

Transport: stateless **Streamable HTTP**, JSON responses, protocols **2025-11-25** and **2025-06-18**. The endpoint is part of the existing Flask application; no extra daemon, local model or production dependency is needed. GET/SSE and DELETE return 405. Supported methods: `initialize`, `ping`, `tools/list`, `tools/call`; notifications return 202. No resources, prompts, server-initiated requests, subscriptions or session persistence are advertised.

## Connect

1. Sign in to Joinly and open **Mon espace → Connecter un assistant avec MCP** (`/account/mcp`).
2. Name the client, choose permissions and create a token. Copy it immediately: it is displayed once.
3. In a client supporting Streamable HTTP and manual bearer authentication, configure the URL above and the header `Authorization: Bearer YOUR_JOINLY_TOKEN`.

Generic connection values (translate the keys to your client's configuration format):

```json
{
  "url": "https://isep.wangjiahan.com/mcp",
  "headers": {"Authorization": "Bearer YOUR_JOINLY_TOKEN"}
}
```

This is a **Joinly token**, not the DeepSeek API key. There is no OAuth discovery or automatic login flow in this version; clients requiring OAuth-only remote connections are not supported. Tokens expire after 30 days, can be revoked and are invalidated by email/password changes or account suspension. A maximum of 10 active tokens per account is allowed. No administrator-wide access exists.

## Tools and permissions

| Tool | Permission | Behavior |
|---|---|---|
| `search_activities` | public:read | Keywords, location, category, date range (Paris), price in cents, pagination; published upcoming activities with places only. |
| `get_activity` | public:read | Public details, availability, cancellation policy, demo flag. |
| `search_faq` | public:read | Published FAQ only. |
| `my_bookings` | bookings:read | Token owner's upcoming/history/all registrations; no email, password or ticket token. |
| `book_activity` | bookings:write | Creates/reuses a 15-minute booking proposal with a confirmation URL. **Does not reserve a seat.** |
| `get_booking_request` | bookings:write | Reads that token owner's proposal status after website confirmation. |

Relative URLs are resolved against the Joinly origin. Token permissions are filtered both at discovery and execution. User identity is always derived from the bearer token or browser session, never from model arguments. Public tools also require a token on the MCP endpoint; the website chat permits anonymous public searches.

## Booking flow

The client calls `book_activity` after the user chooses an activity. `awaiting_confirmation` means no reservation exists yet. The user opens `confirmation_url`, signs into the same account, checks date, location, price and cancellation terms, and confirms in the CSRF-protected website form. Paid activities currently use **simulated payment only**.

Confirmation rejects expired or changed offers, revoked source tokens, other users, closed/cancelled/full activities and unacknowledged paid bookings. Row locks protect the final place and repeated confirmation does not create another registration. Website and assistant confirmations share `app/bookings.py`; tickets and notifications follow the existing booking flow. `get_booking_request` distinguishes pending, expired, confirmed and subsequently cancelled bookings.

## Chatbot integration

The widget uses DeepSeek tool calls and the same `ToolService` directly, avoiding HTTP calls back into its own limited worker pool. The server allows at most 3 provider passes and 4 tools within a 20-second budget. Public context and tool results are untrusted reference data. The private-bookings checkbox, unchecked by default, enables reading the current user's registrations and preparing proposals; changing it clears history. Impersonated sessions cannot use private tools or create tokens.

## Operations and verification

Apply migrations 018 and 019 before deploying. `flask cleanup` removes proposals and token records expired/revoked for more than 30 days. MCP is limited to 60 requests/token/minute, 16 KB request bodies, bounded query sizes and validated origins. Only bearer-token `/mcp` is CSRF-exempt; browser token management and booking confirmation remain protected. Tokens and conversation contents must never enter logs or Git.

Run `pytest` and `python tests/mcp_sdk_smoke.py` (official MCP Python SDK, development dependency). The SDK smoke test starts a temporary local server against `joinly_test`, creates an isolated fixture, verifies discovery/search/booking preparation/confirmation/status and revocation, then deletes its fixture. Never run it concurrently with pytest, which resets the test database.

Protocol references: [Streamable HTTP](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports), [tools](https://modelcontextprotocol.io/specification/2025-11-25/server/tools), [DeepSeek tool calls](https://api-docs.deepseek.com/guides/tool_calls/).
