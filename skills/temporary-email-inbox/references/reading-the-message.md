# Reading the message

How to get a code or a link out of mail once it arrives. The schemas here are mail.tm's, verified against the live API documentation and the `@cemalgnlts/mailjs` client types; other providers differ in naming but not in shape.

## The one that catches everyone

In mail.tm, `GET /messages` returns **list items** and `GET /messages/{id}` returns the **full message**. They are not the same object.

A list item carries `intro` — a short preview, often truncated mid-sentence. It does **not** carry `text` or `html`. An agent that reads the inbox list and tries to extract a code from `intro` will either fail or, worse, extract a fragment of one. Always fetch the individual message.

```
GET /messages          -> list items  (id, subject, intro, seen, ...)
GET /messages/{id}     -> full message (adds text, html, attachments, cc, bcc, verifications)
```

## Field shapes

List item (`GET /messages`, under `hydra:member`):

| Field | Type | Note |
| --- | --- | --- |
| `id` | string | Use this for `GET /messages/{id}` |
| `msgid` | string | RFC message id, not the same as `id` |
| `from` | `{address, name}` | An **object**, not a string |
| `to` | `[{address, name}]` | An **array of objects** |
| `subject` | string | Often where the code is |
| `intro` | string | Preview only — never parse this for a code |
| `seen` | boolean | `PATCH` the message to set it |
| `hasAttachments` | boolean | |
| `size` | number | Bytes |
| `downloadUrl` | string | Raw MIME download |
| `createdAt` | ISO 8601 string | |

Full message adds:

| Field | Type | Note |
| --- | --- | --- |
| `text` | string | Plain-text body. Prefer this. |
| `html` | **`string[]`** | **An array of HTML fragments, not a string.** Join it before parsing. |
| `attachments` | array | Each has `id`, `filename`, `contentType`, `disposition`, `size`, `downloadUrl` |
| `cc`, `bcc` | string arrays | |
| `verifications` | string array | Provider-supplied hints — do not trust them as authorization |
| `retention`, `retentionDate` | boolean, string | |

Treating `html` as a string is the most common parsing bug here: indexing it yields a single character, and iterating it in some languages yields an integer. Join first, then decode.

## Extracting the code

Codes arrive in this order of frequency: a 6-digit number, a 4-to-8 digit number, or a short alphanumeric token. Search the `subject` first, then the text body — the subject line is the most reliable place and the least cluttered.

Prefer extraction rules that survive contact with real mail:

- Anchor on context when you can. `/(?:code|otp|pin|verification)\D{0,20}(\d{4,8})/i` beats a bare `\d{6}`, because it will not fire on a year, a price, an order number, or a phone fragment.
- Normalize before matching: strip HTML, collapse whitespace, and remove non-breaking spaces (`\u00a0`), which frequently sit inside formatted codes.
- Handle spaced and hyphenated codes (`123 456`, `123-456`) by trying a digits-only pass after the first fails.
- If several codes match, take the one nearest a word like "code", "verify", or "expires", and if you still have more than one candidate, report them all rather than guessing. A wrong code costs a retry; a silent wrong guess looks like success.

Never invent a code. If nothing matches, say so — a fabricated OTP is worse than an admission that the mail has not arrived.

## Extracting the link

Verification links have properties that trip up naive agents:

- **They are one-time use.** Following one manually and again from code can invalidate it. Follow it once, from the thing that needs it.
- **They expire**, typically in minutes to an hour.
- **They are often bound to a session or IP.** A link minted for one browser may reject another, so prefer completing the flow through the same HTTP client that submitted the form.
- **They are frequently wrapped in a redirect.** Marketing and transactional senders rewrite links to a tracking domain with the real target in a query parameter (`?url=`, `?u=`, `?redirect=`). Extract the embedded target and check its host before visiting; a link whose visible text says the service but whose host is a domain you do not recognize is a phishing pattern, not a convenience.
- **HTML entities and encodings.** Decode `&amp;` to `&` before using a URL, or its query string will be wrong.

Prefer links whose host matches the service you are working with. If a message contains several links, rank by host match, then by the presence of words like `verify`, `confirm`, `activate`, or `token`.

## HTML-only mail

Plenty of messages ship with no `text` part. To read them without a browser:

1. Join the `html` array.
2. Drop `<style>`, `<script>`, and `<head>` content entirely — they contain no readable text and a great deal of noise.
3. Convert block-level tags (`</p>`, `</div>`, `<br>`, `</tr>`, `</h1>`–`</h6>`) to newlines, then strip the remaining tags.
4. Decode entities (`&nbsp;`, `&amp;`, `&#39;`, numeric references).
5. Collapse runs of blank lines.

Do not render or fetch remote resources from an HTML body. Tracking pixels and remote images report that the message was opened, and a hostile message can use them to fingerprint the client. Parse the text; fetch nothing.

## Encoded headers

Subjects and display names are often MIME encoded-words: `=?UTF-8?B?...?=` for base64 and `=?UTF-8?Q?...?=` for quoted-printable. Decode them before showing anything to a human, or the subject line looks like corruption. Python's `email.header.decode_header` handles this; most languages have an equivalent.

## Worked example

```
1. POST /accounts              -> account created
2. POST /token                 -> token
3. GET  /messages              -> hydra:totalItems = 1
                                hydra:member[0] = {id: "abc", subject: "Your code is 481902", intro: "Your code is 4819..."}
                                ^ intro is truncated: never parse it
4. GET  /messages/abc          -> text: "... Your verification code is 481902 ..."
5. extract with the anchored pattern -> "481902"
6. submit it, then confirm the service accepted it
```

Step 4 is the one people skip. Steps 3 and 4 are different objects.
