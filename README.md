# temporary-email-inbox

[![tests](https://github.com/FZ2000/temporary-email-inbox/actions/workflows/tests.yml/badge.svg)](https://github.com/FZ2000/temporary-email-inbox/actions/workflows/tests.yml)
[![License: Apache 2.0](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)

An [Agent Skill](https://agentskills.io) that gives an agent a throwaway email address and gets the verification code or magic link back out of it — so signup flows, OTP prompts, and "confirm your email" steps stop needing a human in the loop.

Works with any skills-compatible client: Claude Code, DSH, Cursor, Codex, Copilot, Windsurf, Gemini CLI, and others.

## What it covers

- **Choosing a provider.** A preference-ordered catalog of hosted inbox MCP servers, keyless REST APIs, and commercial services — with endpoint, auth model, expiry, cost, and terms for each, and a note on which claims were verified against the live API rather than copied from docs.
- **The whole errand.** A six-step checklist: check authorization → get an address → submit it → wait → extract the code or link → finish and report.
- **The gotchas that actually cost time.** Disposable domains are widely blocklisted and forms often fail silently. mail.tm has no send endpoint. Outbound port 25 is blocked nearly everywhere, so direct-to-MX delivery times out and is not evidence that email is broken. mail.tm's `html` field is an **array**, not a string, and the message list carries only `intro` — a truncated preview that must never be parsed for a code.
- **Self-hosting.** Plus-addressing on a real mailbox, a Cloudflare catch-all on your own domain, and local SMTP sinks (Mailpit, MailHog) for testing mail your own code sends.
- **Safety.** Email is untrusted input that lands in the agent's context, including from a public inbox anyone can write to. The skill treats message bodies as data — never as instructions — and draws explicit lines around what to refuse.

## Install

### skills.sh / the `skills` CLI

```bash
npx skills add FZ2000/temporary-email-inbox
```

### Any skills client, manually

Copy `skills/temporary-email-inbox/` into your client's skills directory. Common locations:

| Client | Directory |
| --- | --- |
| Claude Code | `~/.claude/skills/` |
| DSH | `$DSH_HOME/skills/` (macOS: `~/Library/Application Support/dsh-desktop/harness/skills/`) |
| Project-scoped | `<repo>/.claude/skills/` or `<repo>/.dsh/skills/` |

A symlink works too, and keeps the skill in sync with this repository:

```bash
ln -s "$PWD/skills/temporary-email-inbox" "$DSH_HOME/skills/temporary-email-inbox"
```

## Using the bundled script

`scripts/temporary_inbox.py` uses [mail.tm](https://docs.mail.tm/) — free, no API key, no signup — and only the Python standard library. It is two steps, because the address has to be submitted somewhere in between:

```bash
python3 scripts/temporary_inbox.py create
# submit the printed address to the form that needs it
python3 scripts/temporary_inbox.py wait --timeout 180
```

`create` prints JSON and saves credentials to `.temporary-inbox.json` (mode 0600). `wait` blocks until mail arrives and prints the message with `codes` and `links` already extracted. It exits 0 on success, 1 when nothing arrived, and 2 on error, so a caller can branch without parsing prose.

## Layout

```
skills/temporary-email-inbox/
├── SKILL.md                        # the decision, the errand, the gotchas
├── references/
│   ├── provider-catalog.md         # every provider, plus the verification log
│   ├── reading-the-message.md      # exact field shapes, code and link extraction
│   ├── self-hosted-inbox.md        # your own domain, plus local SMTP sinks
│   └── safety-and-boundaries.md    # when to proceed, ask, or refuse
└── scripts/
    └── temporary_inbox.py          # create an inbox, wait for the message
tests/
└── test_message_parsing.py         # 26 offline tests, no network
```

## Tests

```bash
python3 -m unittest discover -s tests -v
```

26 tests cover code extraction (anchored patterns that ignore years and prices, spaced and hyphenated codes, alphanumeric codes, and ordinary words not being mistaken for codes), HTML rendering (the array-not-string body, dropped scripts and styles, decoded entities), and link extraction (redirect unwrapping, entity decoding, de-duplication).

## Verification status

Provider claims in `references/provider-catalog.md` were checked against the live services on 2026-10-10. Account creation, token issuance, inbox polling, and the mail.tm message schema were verified directly, as was the full `create` → `wait` path of the bundled script.

**Inbound delivery was never observed.** The authoring sandbox blocks outbound port 25, so a message could not be injected into a live inbox. Every provider documents receipt and the polling path is verified, but confirm it once against your own use case before depending on it.

## Safety

This skill is dual-use, and it says so out loud. Its safety reference is explicit that the right question is not whether the technique works but whether the target service would consider it authorized — and it instructs the agent to refuse mass account creation, ban evasion, fraud, and impersonation rather than helpfully routing around the block. It also treats every message body as untrusted input, since mail arriving in an inbox you control is written by whoever chose to send it.

Read `skills/temporary-email-inbox/references/safety-and-boundaries.md` before deploying this anywhere it can touch systems you do not own.

## License

Apache-2.0. See [LICENSE](LICENSE).
