"""Structural checks for the skill: metadata budgets and reference-file drift.

These guard the two failure modes that are silent otherwise:

* a skill body over the harness pruning threshold, whose middle is replaced by a
  marker during compaction with no error at all;
* a SKILL.md that points at a reference file which has been renamed or removed,
  so the agent follows a dead path instead of the detail.

Run from the repository root:

    python3 -m unittest discover -s tests -v
"""

from __future__ import annotations

import os
import re
import unittest

try:
    import yaml
except ImportError:  # pragma: no cover - the check is skipped without it
    yaml = None

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL_DIR = os.path.join(REPO_ROOT, "skills", "temporary-email-inbox")
SKILL_FILE = os.path.join(SKILL_DIR, "SKILL.md")

# The DSH standard preset mounts a tool-result pruner at this threshold, and the
# skill tool gets no exemption. Past it, a compacted session loses the middle of
# the body silently.
PRUNING_THRESHOLD = 8192

# The DSH catalog truncates a description at max - 3 characters plus "...".
CATALOG_DESCRIPTION_BUDGET = 500

# The Agent Skills specification's hard limit.
SPEC_DESCRIPTION_LIMIT = 1024

NAME_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
PATH_MENTION_PATTERN = re.compile(r"`((?:references|scripts|assets)/[^`]+)`")


def read_skill():
    with open(SKILL_FILE, encoding="utf-8") as handle:
        return handle.read()


def split_frontmatter(text):
    match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not match:
        raise AssertionError("SKILL.md must start with a --- delimited frontmatter block")
    return match.group(1), text[match.end():]


def frontmatter_value(frontmatter, key):
    match = re.search(rf"^{key}:\s*(.*)$", frontmatter, re.MULTILINE)
    if not match:
        return None
    value = match.group(1).strip()
    # A value may be quoted to protect colons or leading punctuation.
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
        value = value[1:-1].replace(value[0] * 2, value[0])
    return value


class Metadata(unittest.TestCase):
    def setUp(self):
        self.frontmatter, self.body = split_frontmatter(read_skill())
        self.name = frontmatter_value(self.frontmatter, "name")
        self.description = frontmatter_value(self.frontmatter, "description")

    def test_name_is_present_and_kebab_case(self):
        self.assertIsNotNone(self.name)
        self.assertRegex(self.name, NAME_PATTERN)

    def test_name_is_within_the_specification_limit(self):
        self.assertLessEqual(len(self.name), 64)

    def test_name_matches_the_directory_it_lives_in(self):
        self.assertEqual(self.name, os.path.basename(SKILL_DIR))

    def test_description_is_present_and_non_empty(self):
        self.assertTrue(self.description and self.description.strip())

    def test_description_fits_the_dsh_catalog_budget(self):
        self.assertLess(
            len(self.description),
            CATALOG_DESCRIPTION_BUDGET - 3,
            f"description is {len(self.description)} chars; DSH would truncate it mid-sentence",
        )

    def test_description_fits_the_specification_limit(self):
        self.assertLessEqual(len(self.description), SPEC_DESCRIPTION_LIMIT)

    def test_no_legacy_camel_case_invocation_keys(self):
        for legacy in ("disableModelInvocation", "modelInvocable", "userInvocable"):
            self.assertNotIn(legacy, self.frontmatter, f"{legacy} causes the skill to be dropped")

    def test_body_stays_under_the_pruning_threshold(self):
        total = len(read_skill())
        self.assertLess(
            total,
            PRUNING_THRESHOLD,
            f"SKILL.md is {total} bytes; a compacted session would lose its middle",
        )

    def test_body_is_not_a_stub(self):
        self.assertGreater(len(self.body), 1500, "body looks too thin to be worth a catalog slot")


@unittest.skipUnless(yaml is not None, "PyYAML is not installed")
class FrontmatterParsesAsYaml(unittest.TestCase):
    """A plain scalar containing ": " is invalid YAML and the whole skill is dropped.

    Discovery is lenient in the worst way: a malformed entry disappears with only a
    log warning, so the skill simply is not there and the catalog cannot tell you why.
    """

    def test_frontmatter_is_valid_yaml(self):
        frontmatter, _ = split_frontmatter(read_skill())
        try:
            parsed = yaml.safe_load(frontmatter)
        except yaml.YAMLError as error:
            self.fail(f"frontmatter is not valid YAML, so the skill would be dropped: {error}")
        self.assertIsInstance(parsed, dict)

    def test_parsed_values_match_the_raw_fields(self):
        frontmatter, _ = split_frontmatter(read_skill())
        parsed = yaml.safe_load(frontmatter)
        self.assertEqual(parsed["name"], frontmatter_value(frontmatter, "name"))
        self.assertEqual(parsed["description"], frontmatter_value(frontmatter, "description"))
        self.assertTrue(parsed["description"].strip())

    def test_metadata_is_an_object_if_present(self):
        frontmatter, _ = split_frontmatter(read_skill())
        parsed = yaml.safe_load(frontmatter)
        if "metadata" in parsed:
            self.assertIsInstance(parsed["metadata"], dict)


class ReferenceDrift(unittest.TestCase):
    def setUp(self):
        self.body = split_frontmatter(read_skill())[1]
        self.mentioned = set(PATH_MENTION_PATTERN.findall(self.body))

    def test_every_referenced_file_exists(self):
        for relative_path in sorted(self.mentioned):
            with self.subTest(path=relative_path):
                self.assertTrue(
                    os.path.isfile(os.path.join(SKILL_DIR, relative_path)),
                    f"SKILL.md points at {relative_path}, which does not exist",
                )

    def test_no_reference_file_is_orphaned(self):
        on_disk = set()
        for directory in ("references", "scripts"):
            full = os.path.join(SKILL_DIR, directory)
            if not os.path.isdir(full):
                continue
            for entry in sorted(os.listdir(full)):
                if entry.startswith((".", "__")):
                    continue
                on_disk.add(f"{directory}/{entry}")
        unreferenced = on_disk - self.mentioned
        self.assertEqual(
            unreferenced, set(),
            f"these files exist but SKILL.md never points at them: {sorted(unreferenced)}",
        )

    def test_every_reference_file_has_some_substance(self):
        for relative_path in sorted(self.mentioned):
            with self.subTest(path=relative_path):
                full = os.path.join(SKILL_DIR, relative_path)
                with open(full, encoding="utf-8") as handle:
                    self.assertGreater(len(handle.read()), 500)


if __name__ == "__main__":
    unittest.main()
