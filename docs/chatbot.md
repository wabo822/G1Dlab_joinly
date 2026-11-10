# Joinly Assistant

The global bottom-right widget uses POST `/api/assistant` with CSRF protection. Set `DEEPSEEK_API_KEY` and optionally `DEEPSEEK_MODEL` (default `deepseek-flash`) in `/etc/joinly.env`, then restart `joinly`. No new service, SDK, vector database or local model is needed.

Context: `app/assistant_context.md`, current time/booking cutoff, up to 12 published future activities with availability and prices, and 6 published FAQ entries. Selection uses message keywords and optionally interests; it is not an exhaustive search or a booking guarantee. The assistant has no action tools. It can answer in the visitor's language, explain Joinly and discuss general questions without live web access.

Visitors must accept transmission to DeepSeek before sending. Interests and chosen area require both saved account permission and the chat checkbox. Impersonation never includes profile context. Account identifiers, emails, reservations and private drafts are not supplied. Conversation text is not stored by Joinly; recent history lives in page memory and is cleared on navigation or Effacer. Provider processing remains subject to its own terms.

Limits: 1,200 characters/message, 8 historical messages accepted (UI sends 6), 700 output tokens, 18-second provider socket timeout, 10 requests/IP/15 minutes, 30/account/hour, 100/site/rolling 24 hours. PostgreSQL advisory lock allows only one upstream request at a time, leaving another Gunicorn worker available. Quotas share the existing rate_limits table; no in-memory model or extra dependency. These conservative limits can be adjusted in `app/chatbot.py` and `CHAT_DAILY_LIMIT` in app config.

The API key stays server-side. Responses render as plain text with server-allowlisted internal links only. Provider errors return a generic message; neither keys nor upstream bodies are logged. Apply migration 017 to publish the updated privacy notice while preserving unrelated existing text.
