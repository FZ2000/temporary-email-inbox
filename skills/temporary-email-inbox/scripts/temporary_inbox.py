#!/usr/bin/env python3
"""Create a temporary inbox, then wait for the message that arrives in it.

Two steps, because the address has to be submitted somewhere in between:

    temporary_inbox.py create                 # prints an address, saves state
    # ... submit the address to the form that needs it ...
    temporary_inbox.py wait --timeout 180     # blocks, then prints the mail

Uses mail.tm: free, no API key, no signup. Standard library only.
Terms: 8 queries/second per IP, visible attribution required, no proxying.
"""

from __future__ import annotations

import argparse
import html as html_module
import json
import os
import random
import re
import string
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

API_BASE = "https://api.mail.tm"
DEFAULT_STATE_FILE = ".temporary-inbox.json"
DEFAULT_WAIT_SECONDS = 180
DEFAULT_POLL_SECONDS = 4

# A code is usually introduced by one of these words. Anchoring on them avoids
# matching years, prices and order numbers, which a bare \d{6} happily would.
CODE_CONTEXT = r"(?:code|otp|pin|passcode|verification|verify|one[- ]?time|security)"
CODE_PATTERNS = (
    re.compile(CODE_CONTEXT + r"\D{0,24}(\d{4,8})\b", re.IGNORECASE),
    # An alphanumeric code must contain a digit, or "verification link below"
    # would hand back the word "below" as the code. The leading \b stops the gap
    # from swallowing the code's first letter on its way to the digits.
    re.compile(CODE_CONTEXT + r"\D{0,24}\b((?=[A-Za-z0-9]*\d)[A-Za-z0-9]{5,8})\b", re.IGNORECASE),
    re.compile(r"\b(\d{6})\b"),
    re.compile(r"\b(\d{4,8})\b"),
)

# Query parameters that commonly wrap the real destination of a tracked link.
REDIRECT_PARAMETERS = ("url", "u", "redirect", "redirect_uri", "target", "continue", "q", "link")

URL_PATTERN = re.compile(r"https?://[^\s<>\"'\)\]]+")
HTML_HREF_PATTERN = re.compile(r"""href\s*=\s*["']([^"']+)["']""", re.IGNORECASE)
BLOCK_TAG_PATTERN = re.compile(
    r"</(?:p|div|tr|td|th|li|ul|ol|h[1-6]|table|blockquote|section|article|header|footer)\s*>"
    r"|<br\s*/?>",
    re.IGNORECASE,
)
DROP_ELEMENT_PATTERN = re.compile(r"<(script|style|head)\b.*?</\1>", re.IGNORECASE | re.DOTALL)
ANY_TAG_PATTERN = re.compile(r"<[^>]+>")
BLANK_RUN_PATTERN = re.compile(r"\n{3,}")


class MailTmError(RuntimeError):
    """A non-2xx response from mail.tm, carrying its error body."""


def request_json(path, *, method="GET", body=None, token=None, timeout=30):
    """Call the mail.tm API and return the decoded JSON body."""
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(API_BASE + path, data=data, method=method)
    request.add_header("Accept", "application/json")
    if data is not None:
        request.add_header("Content-Type", "application/json")
    if token:
        request.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", "replace")[:400]
        raise MailTmError(f"{method} {path} -> HTTP {error.code}: {detail}") from error
    except urllib.error.URLError as error:
        raise MailTmError(f"{method} {path} -> network error: {error.reason}") from error
    if not payload.strip():
        return {}
    return json.loads(payload)


def hydra_members(payload):
    """Read a Hydra collection's items, tolerating a bare list."""
    if isinstance(payload, list):
        return payload
    return payload.get("hydra:member") or []


def plain_text_from_html(fragments):
    """Turn mail.tm's html array into readable text. The field is a list, not a string."""
    if isinstance(fragments, str):
        fragments = [fragments]
    joined = "\n".join(fragment for fragment in (fragments or []) if fragment)
    joined = DROP_ELEMENT_PATTERN.sub(" ", joined)
    joined = BLOCK_TAG_PATTERN.sub("\n", joined)
    joined = ANY_TAG_PATTERN.sub(" ", joined)
    joined = html_module.unescape(joined)
    joined = joined.replace("\u00a0", " ").replace("\r\n", "\n")
    joined = "\n".join(line.strip() for line in joined.split("\n"))
    return BLANK_RUN_PATTERN.sub("\n\n", joined).strip()


def normalize_for_matching(text):
    """Collapse whitespace and strip the separators that sit inside formatted codes."""
    text = text.replace("\u00a0", " ")
    text = re.sub(r"(?<=\d)[\s\-](?=\d)", "", text)
    return re.sub(r"[ \t]+", " ", text)


def extract_codes(*texts):
    """Find verification codes, most trustworthy pattern first."""
    found = []
    for text in texts:
        if not text:
            continue
        candidate_text = normalize_for_matching(text)
        for pattern in CODE_PATTERNS:
            for match in pattern.finditer(candidate_text):
                value = match.group(1)
                if value not in found:
                    found.append(value)
            if found:
                return found
    return found


def unwrap_redirect(url):
    """Follow a tracking wrapper to the address embedded in its query string."""
    try:
        parts = urllib.parse.urlsplit(url)
    except ValueError:
        return url
    if not parts.query:
        return url
    parameters = urllib.parse.parse_qs(parts.query)
    for name in REDIRECT_PARAMETERS:
        for value in parameters.get(name, []):
            candidate = urllib.parse.unquote(value).strip()
            if candidate.startswith(("http://", "https://")):
                return candidate
    return url


def extract_links(*texts, html_fragments=None):
    """Collect links, preferring the real destination over a tracking wrapper."""
    raw = []
    for text in texts:
        if text:
            raw.extend(URL_PATTERN.findall(text))
    for fragment in html_fragments or []:
        raw.extend(HTML_HREF_PATTERN.findall(fragment or ""))

    links = []
    for candidate in raw:
        cleaned = html_module.unescape(candidate).rstrip(".,;:")
        target = unwrap_redirect(cleaned)
        if target not in links:
            links.append(target)
    return links


def message_summary(message, include_body=True):
    """Flatten one message into the fields an agent actually needs."""
    html_fragments = message.get("html") or []
    text = message.get("text") or ""
    if not text and html_fragments:
        text = plain_text_from_html(html_fragments)
    sender = message.get("from") or {}
    recipients = message.get("to") or []
    summary = {
        "id": message.get("id"),
        "from": sender.get("address") if isinstance(sender, dict) else sender,
        "to": [item.get("address") if isinstance(item, dict) else item for item in recipients],
        "subject": message.get("subject"),
        "received_at": message.get("createdAt"),
        "codes": extract_codes(message.get("subject") or "", text),
        "links": extract_links(text, html_fragments=html_fragments),
        "attachments": [
            {"filename": item.get("filename"), "content_type": item.get("contentType")}
            for item in (message.get("attachments") or [])
        ],
    }
    if include_body:
        summary["text"] = text
    return summary


def load_state(path):
    if not path or not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def save_state(path, state):
    if not path:
        return
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(state, handle, indent=2)
    os.chmod(path, 0o600)


def random_local_part():
    return "inbox" + "".join(random.choices(string.ascii_lowercase + string.digits, k=10))


def random_password():
    return "".join(random.choices(string.ascii_letters + string.digits, k=16))


def create_account(address=None, domain=None):
    """Register a throwaway mailbox and return its credentials."""
    if not address:
        if not domain:
            domains = hydra_members(request_json("/domains"))
            if not domains:
                raise MailTmError("no domains are available from mail.tm right now")
            domain = domains[0]["domain"]
        address = f"{random_local_part()}@{domain}"
    password = random_password()
    account = request_json("/accounts", method="POST", body={"address": address, "password": password})
    token = request_json("/token", method="POST", body={"address": address, "password": password})["token"]
    return {
        "address": address,
        "password": password,
        "token": token,
        "account_id": account.get("id"),
        "expires": "deleted when the account is deleted; mail.tm keeps it until then",
    }


def fetch_messages(token):
    listed = hydra_members(request_json("/messages", token=token))
    full = []
    for item in listed:
        try:
            full.append(request_json(f"/messages/{item['id']}", token=token))
        except MailTmError:
            full.append(item)
    return full


def command_create(arguments):
    state = create_account(arguments.address, arguments.domain)
    save_state(arguments.state_file, state)
    state["state_file"] = arguments.state_file if arguments.state_file else None
    state["next"] = "Submit this address, then run: temporary_inbox.py wait --timeout 180"
    print(json.dumps(state, indent=2))
    return 0


def command_wait(arguments):
    state = load_state(arguments.state_file)
    address = arguments.address or state.get("address")
    password = arguments.password or state.get("password")
    token = state.get("token")
    if not address:
        print(json.dumps({"error": "no address: pass --address/--password or run create first"}), file=sys.stderr)
        return 2
    if not token:
        if not password:
            print(json.dumps({"error": "no credentials for that address"}), file=sys.stderr)
            return 2
        token = request_json("/token", method="POST", body={"address": address, "password": password})["token"]

    deadline = time.monotonic() + arguments.timeout
    messages = []
    while True:
        messages = fetch_messages(token)
        if messages or time.monotonic() >= deadline:
            break
        time.sleep(arguments.interval)

    if not messages:
        print(json.dumps({
            "address": address,
            "messages": [],
            "note": (
                "No mail arrived in {0}s. Before debugging the plumbing, suspect the domain: "
                "many signup forms silently refuse disposable addresses.".format(arguments.timeout)
            ),
        }, indent=2))
        return 1

    ordered = sorted(messages, key=lambda item: item.get("createdAt") or "")
    if not arguments.all:
        ordered = ordered[-1:]
    print(json.dumps({
        "address": address,
        "messages": [message_summary(message) for message in ordered],
    }, indent=2))
    return 0


def build_parser():
    parser = argparse.ArgumentParser(
        description="Create a temporary inbox and read the message that arrives in it.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    create = subparsers.add_parser("create", help="register a throwaway address")
    create.add_argument("--address", help="request a specific address instead of a random one")
    create.add_argument("--domain", help="pick a domain from GET /domains")
    create.add_argument("--state-file", default=DEFAULT_STATE_FILE,
                        help=f"where to save credentials (default {DEFAULT_STATE_FILE})")
    create.set_defaults(handler=command_create)

    wait = subparsers.add_parser("wait", help="block until mail arrives, then print it")
    wait.add_argument("--address", help="reuse an address from a previous create")
    wait.add_argument("--password", help="password for that address")
    wait.add_argument("--state-file", default=DEFAULT_STATE_FILE,
                      help=f"credentials saved by create (default {DEFAULT_STATE_FILE})")
    wait.add_argument("--timeout", type=int, default=DEFAULT_WAIT_SECONDS,
                      help=f"seconds to wait (default {DEFAULT_WAIT_SECONDS})")
    wait.add_argument("--interval", type=float, default=DEFAULT_POLL_SECONDS,
                      help=f"seconds between checks (default {DEFAULT_POLL_SECONDS}; keeps under 8 QPS)")
    wait.add_argument("--all", action="store_true", help="print every message, not just the newest")
    wait.set_defaults(handler=command_wait)

    return parser


def main(argv=None):
    arguments = build_parser().parse_args(argv)
    try:
        return arguments.handler(arguments)
    except MailTmError as error:
        print(json.dumps({"error": str(error)}), file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
