"""Deterministic tests for the message parsing, with no network access.

Run from the repository root:

    python3 -m unittest discover -s tests -v
"""

from __future__ import annotations

import os
import sys
import unittest

SCRIPTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "skills",
    "temporary-email-inbox",
    "scripts",
)
sys.path.insert(0, SCRIPTS_DIR)

import temporary_inbox  # noqa: E402


class CodeExtraction(unittest.TestCase):
    def test_code_announced_in_context_beats_stray_numbers(self):
        body = "Order 2024 shipped, total 1499. Your verification code is 481902."
        self.assertEqual(temporary_inbox.extract_codes(body), ["481902"])

    def test_code_split_by_spaces_is_rejoined(self):
        self.assertEqual(temporary_inbox.extract_codes("Your code is 123 456"), ["123456"])

    def test_code_split_by_a_hyphen_is_rejoined(self):
        self.assertEqual(temporary_inbox.extract_codes("Your code is 123-456"), ["123456"])

    def test_non_breaking_space_inside_a_code(self):
        self.assertEqual(temporary_inbox.extract_codes("code:\u00a0998877"), ["998877"])

    def test_alphanumeric_code_is_found(self):
        self.assertEqual(temporary_inbox.extract_codes("Your OTP is A1B2C3"), ["A1B2C3"])

    def test_ordinary_words_are_not_mistaken_for_codes(self):
        self.assertEqual(temporary_inbox.extract_codes("Use the verification link below"), [])

    def test_subject_is_searched_before_body(self):
        found = temporary_inbox.extract_codes("Your code is 111222", "Invoice 333444 attached")
        self.assertEqual(found, ["111222"])

    def test_no_code_at_all_returns_empty(self):
        self.assertEqual(temporary_inbox.extract_codes("Welcome aboard!", ""), [])


class HtmlRendering(unittest.TestCase):
    def test_html_field_is_an_array_not_a_string(self):
        rendered = temporary_inbox.plain_text_from_html(["<p>Your code is <b>998877</b></p>"])
        self.assertIn("998877", rendered)

    def test_a_string_is_tolerated(self):
        self.assertIn("hello", temporary_inbox.plain_text_from_html("<div>hello</div>"))

    def test_style_and_script_are_dropped(self):
        rendered = temporary_inbox.plain_text_from_html(
            ["<style>.a{color:red}</style><script>alert(1)</script><p>Visible</p>"]
        )
        self.assertIn("Visible", rendered)
        self.assertNotIn("color:red", rendered)
        self.assertNotIn("alert", rendered)

    def test_entities_are_decoded(self):
        rendered = temporary_inbox.plain_text_from_html(["<p>Tom &amp; Jerry &#39;quoted&#39;</p>"])
        self.assertIn("Tom & Jerry 'quoted'", rendered)

    def test_block_tags_become_line_breaks(self):
        rendered = temporary_inbox.plain_text_from_html(["<p>one</p><p>two</p>"])
        self.assertEqual(rendered, "one\ntwo")

    def test_remote_resources_are_not_fetched(self):
        rendered = temporary_inbox.plain_text_from_html(['<img src="https://tracker.example/p.gif">'])
        self.assertNotIn("tracker.example", rendered)


class LinkExtraction(unittest.TestCase):
    def test_link_is_found_in_plain_text(self):
        links = temporary_inbox.extract_links("Verify at https://acme.example/verify?t=1 now")
        self.assertEqual(links, ["https://acme.example/verify?t=1"])

    def test_link_is_found_in_an_href_attribute(self):
        links = temporary_inbox.extract_links("", html_fragments=['<a href="https://acme.example/v">go</a>'])
        self.assertIn("https://acme.example/v", links)

    def test_escaped_ampersand_is_decoded(self):
        links = temporary_inbox.extract_links("https://acme.example/v?a=1&amp;b=2")
        self.assertEqual(links, ["https://acme.example/v?a=1&b=2"])

    def test_tracking_wrapper_is_unwrapped(self):
        wrapped = (
            "https://click.tracker.example/ls/click?upn=abc"
            "&url=https%3A%2F%2Facme.example%2Fverify%3Ft%3D9"
        )
        self.assertEqual(temporary_inbox.extract_links(wrapped), ["https://acme.example/verify?t=9"])

    def test_duplicates_are_removed(self):
        links = temporary_inbox.extract_links("https://a.example/x https://a.example/x")
        self.assertEqual(links, ["https://a.example/x"])

    def test_trailing_punctuation_is_trimmed(self):
        self.assertEqual(temporary_inbox.extract_links("See https://a.example/x."), ["https://a.example/x"])


class MessageSummary(unittest.TestCase):
    def test_fields_are_flattened_to_plain_strings(self):
        summary = temporary_inbox.message_summary({
            "id": "abc",
            "from": {"address": "no-reply@acme.example", "name": "Acme"},
            "to": [{"address": "inbox@mail.tm", "name": ""}],
            "subject": "Your code is 481902",
            "text": "Enter 481902 to continue.",
            "createdAt": "2026-10-10T21:00:00+00:00",
        })
        self.assertEqual(summary["from"], "no-reply@acme.example")
        self.assertEqual(summary["to"], ["inbox@mail.tm"])
        self.assertEqual(summary["codes"], ["481902"])

    def test_html_only_message_still_yields_text_and_codes(self):
        summary = temporary_inbox.message_summary({
            "subject": "Confirm your address",
            "html": ["<p>Your code is <strong>554433</strong></p>", "<a href='https://acme.example/c'>Confirm</a>"],
        })
        self.assertIn("554433", summary["text"])
        self.assertEqual(summary["codes"], ["554433"])
        self.assertIn("https://acme.example/c", summary["links"])

    def test_attachments_are_listed(self):
        summary = temporary_inbox.message_summary({
            "subject": "Invoice",
            "text": "attached",
            "attachments": [{"filename": "invoice.pdf", "contentType": "application/pdf"}],
        })
        self.assertEqual(summary["attachments"], [{"filename": "invoice.pdf", "content_type": "application/pdf"}])


class HydraCollections(unittest.TestCase):
    def test_members_are_read_from_a_hydra_collection(self):
        payload = {"hydra:totalItems": 1, "hydra:member": [{"id": "a"}]}
        self.assertEqual(temporary_inbox.hydra_members(payload), [{"id": "a"}])

    def test_a_bare_list_is_accepted(self):
        self.assertEqual(temporary_inbox.hydra_members([{"id": "a"}]), [{"id": "a"}])

    def test_an_empty_collection_is_empty(self):
        self.assertEqual(temporary_inbox.hydra_members({"hydra:member": []}), [])


if __name__ == "__main__":
    unittest.main()
