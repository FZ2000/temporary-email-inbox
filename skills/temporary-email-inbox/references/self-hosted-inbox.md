# Self-hosted inbox

Reach for this when a disposable domain will not do: the service you are signing up to rejects known throwaway domains, the address has to keep working for password resets, or an agent needs a stable identity rather than a new address per task.

The trade is real. You take on a domain, MX records, and a place to store mail, in exchange for an address that no blocklist knows about and that you can audit.

## Option 1 — plus-addressing on a real mailbox

The cheapest thing that is not on any blocklist. Every address at a domain you already own can be tagged:

```
you+signup-acme@yourdomain.com
you+agent-task17@yourdomain.com
```

Mail still lands in your normal inbox, and the agent reads it over IMAP or the provider's API, filtering on the tag. No infrastructure, no new domain, and the address is as reputable as your real one.

Caveats worth knowing before you rely on it: a minority of forms reject `+` in an address or strip the tag, and some providers deliver plus-addressed mail to the same thread, so filtering must be strict. Use a dedicated folder or label so the agent is not reading everything you receive.

## Option 2 — catch-all on your own domain

The durable answer. Receive mail for `anything@inbox.yourdomain.com` and let an agent read it through an endpoint you control.

With Cloudflare, receiving is free and needs only MX records plus a Worker:

1. Add the domain (or a subdomain such as `inbox.yourdomain.com`) to Cloudflare.
2. **Email Routing** → enable → the wizard writes the MX and TXT records for you.
3. Set a **catch-all** rule that routes to a Worker instead of a mailbox.
4. The Worker parses the message and writes it somewhere durable — D1 for queryable storage, KV for simplicity, R2 for raw MIME.
5. Expose a small authenticated read endpoint, and have the agent call that, or wrap it in an MCP server.

Cloudflare publishes a worked example of exactly this shape: `cloudflare/agentic-inbox`, a self-hosted email client with an agent, running entirely on Workers.

Two constraints to plan around:

- **Email Routing receives but does not send.** Sending needs a different mechanism — a transactional provider, or the Workers `send_email` binding with verified destination addresses.
- **A subdomain is worth the small effort.** Keeping agent mail on `inbox.` rather than the apex means a deliverability problem cannot damage your primary domain's reputation.

`Vozec/Tempmail-MCP` and `@arvoretech/tempmail-mcp` both implement hosted variants of this pattern; the first also aggregates public providers, and both are worth reading before writing your own.

## Option 3 — catch SMTP locally when testing your own app

If the goal is checking mail *your own code sends* — not receiving from the outside — do not involve the internet at all. Run a local SMTP sink and point your app's mailer at it:

- **Mailpit** — actively maintained, single binary, HTTP API and web UI
- **MailHog** — the older, widely deployed equivalent
- **Mailcatcher** — Ruby, simple

These accept any SMTP traffic on localhost, store it, and expose it over an HTTP API the agent can read. Tests become deterministic and offline, no address is consumed, and nothing can leak to a third party. This is the right default for QA of transactional email; reach for the hosted providers only when the flow genuinely requires an external address.

## Operating notes for any inbox you own

- **Treat stored mail as untrusted input.** A catch-all accepts mail from anyone who knows the address, and every body is text that an agent will read. See `safety-and-boundaries.md`.
- **Bound retention.** Raw MIME with attachments grows quickly. Set an expiry, and delete messages once the task is finished — a working inbox that accumulates verification links is a standing liability.
- **Authenticate the read endpoint.** An unauthenticated catch-all reader exposes every message the domain has ever received.
- **Receiving needs only MX.** Do not add SPF, DKIM, or DMARC expecting them to help with inbound; they matter for sending, and for telling receivers your outbound mail is legitimate.
- **Do not reuse a domain you care about.** An agent-facing inbox is exposed to the open internet by design. Isolating it on a separate domain or subdomain keeps a compromise contained.
