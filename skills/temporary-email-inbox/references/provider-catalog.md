# Provider catalog

Pick a default and move. The table below is ordered by preference; only go further down when the row above cannot work.

Companion files: `reading-the-message.md` for parsing what arrives, `self-hosted-inbox.md` when the address must not look disposable, `safety-and-boundaries.md` before pointing any of this at a service you do not own.

## Preference order

1. **An inbox MCP tool already in the tool list.** It blocks until mail arrives, so it costs one call instead of a polling loop.
2. **`scripts/temporary_inbox.py`** — mail.tm, no key, no signup, standard library only.
3. **Mailinator's public read API** — any name works instantly, no auth at all. Read the privacy warning before using it for anything.
4. **A commercial provider** — when you need volume, attachments, sending, SMS, or a real support relationship.

## Hosted MCP servers

Install by adding the command to the client's MCP config. All are stdio servers.

| Server | Install | Auth | Notes |
| --- | --- | --- | --- |
| `emptyinbox-mcp` | `npx -y emptyinbox-mcp` | none — self-registers on first use | **Verified working.** 12 tools including `wait_for_message`, which blocks and returns the extracted code. Inboxes last 30 days. Free tier, then credits. Listed in the official MCP registry as `io.github.cnohall/emptyinbox`. |
| Mailinator MCP | `npm i -g mailinator-cli` then `mailinator-cli --start-mcp-server` | none for public inboxes; `MAILINATOR_API_KEY` for private domains | Official Mailinator server. Public inboxes need no auth; private domains are the supported path for OTPs and reset links. |
| `tempmail-mcp` | `npx -y tempmail-mcp` | `TEMPMAIL_API_KEY` (free key) | Purpose-built for signup flows: `wait_for_code` blocks and returns the digits plus the activation link. Mailboxes live 24 hours. 300 new mailboxes/hour, 100 alive. |
| `@mailsac/mcp` | npm package | Mailsac API key | Mailsac's own server, for their paid email-testing service. |
| `Vozec/Tempmail-MCP` | Docker Compose, self-hosted | none | Aggregates mail.tm, tempmail.io, Gmail IMAP and several scraped providers behind one API, exposes `/mcp/`. Auto-disables providers that fail 3× in a row. Best self-hosted generalist. |
| `@arvoretech/tempmail-mcp` | self-hosted | Cloudflare credentials | Cloudflare D1 + Email Workers, on your own domain. Zero infrastructure, but you own the setup. |
| `@pragyanm/temp-mail-mcp-server` | `npx -y @pragyanm/temp-mail-mcp-server` | none | Thin wrapper over mail.tm. Tools: `create_one_account`, `register_account`, `login`, `me`, `get_messages`, `get_message`. **Has no wait tool**, so the agent must poll. |
| `mcp-server-tempmail` | npm / MCP registry | ChatTempMail API | Backed by ChatTempMail. |

## Read APIs with no signup

| Provider | Endpoint | Auth | Notes |
| --- | --- | --- | --- |
| **mail.tm** | `https://api.mail.tm` | none to start; bearer token after account creation | **Verified.** Free, no key, 8 QPS per IP. No send endpoint. Terms require visible attribution and forbid proxying or reselling. |
| **Mailinator public** | `GET https://api.mailinator.com/api/v2/domains/public/inboxes/{name}` | **none** | **Verified.** Any inbox name works instantly, no signup, no token. Returns `{"msgs":[...]}`. |
| mail.gw | `https://api.mail.gw` | same model as mail.tm | mail.tm's sibling project. **Returned HTTP 502 when tested** — treat as unreliable and verify before relying on it. |
| 1secmail | — | — | **Dead.** The legacy API did not respond. Do not use in new work. |

### mail.tm flow (verified end to end)

```
GET  /domains                     -> hydra:member[0].domain   (never hardcode a domain)
POST /accounts   {"address","password"}                        -> 201
POST /token      {"address","password"}                        -> {"token": "..."}
GET  /messages                    Authorization: Bearer <token>
GET  /messages/{id}               Authorization: Bearer <token>
```

Responses are Hydra collections: the payload is under `hydra:member`, with the count in `hydra:totalItems`. A message list item carries only `intro`, a short preview — the body arrives only from `GET /messages/{id}`. See `reading-the-message.md` for the exact field shapes, including the one that catches people.

### Mailinator public inboxes — read this before using one

Any string works as an inbox: nobody registers, nobody owns it, and **anyone who guesses or observes the name can read it**. There is no per-user isolation on the public domain. Use it for throwaway tests where a leak is harmless, never for a password reset on an account that matters, and never for anything containing personal data.

## Commercial providers

| Provider | What you get | When it is worth it |
| --- | --- | --- |
| **MailSlurp** | Real inboxes and phone numbers, send + receive, attachments, scoped MCP access, SDKs in many languages | The agent needs a durable identity, must reply, or reads SMS as well as mail |
| **Mailinator** (private domain) | Your own Mailinator-managed domain, full API, no blocklist exposure | OTP and reset-link automation at volume |
| **Mailsac** | Email-testing API with a long track record | Existing Mailsac user, or need their tooling |

All three have free tiers that are adequate for trying them out.

## Verification log

Checked against the live services on **2026-10-10**:

| Claim | How it was checked | Result |
| --- | --- | --- |
| mail.tm account creation and token | Created a throwaway account, got a 367-char bearer token | Works |
| mail.tm inbox polling | `GET /messages` with the token | Works, returns an empty Hydra collection |
| mail.tm cannot send | `POST /messages` | **HTTP 405** — no send endpoint |
| mail.tm message schema | Parsed the Hydra API documentation at `api.mail.tm/docs.jsonld` and cross-checked against the `@cemalgnlts/mailjs` client types | Field lists confirmed |
| `emptyinbox-mcp` | Ran the server over stdio, listed tools, called `create_inbox` | Works, returned a live address expiring in 30 days |
| Mailinator public read API | `GET .../public/inboxes/{random-name}` with no credentials | HTTP 200 |
| mail.gw | `GET /domains` | HTTP 502 — down at test time |
| 1secmail | legacy endpoint | No response — discontinued |

### What was *not* verified

**Inbound delivery was never observed.** The test sandbox blocks outbound port 25, so direct-to-MX delivery timed out and no message could be injected into a live inbox. Account creation, authentication, polling, and the message schema are verified; the arrival of an actual message is documented by each provider but was not reproduced here. Confirm it once against your own use case before building on it.

## Provider limits worth knowing

- **mail.tm** — 8 queries/second per IP. Reuse one inbox rather than creating one per message. Attribution required, proxying and reselling forbidden.
- **emptyinbox** — free inboxes, then credits. `keep_inbox` costs 30 credits and makes an address permanent; without it the address stops receiving after 30 days.
- **tempmailgenerator.net** — 24-hour mailboxes, 300 created per hour, 100 alive at once.
- **Mailinator public** — fully public, and aggressively blocklisted by signup forms.
