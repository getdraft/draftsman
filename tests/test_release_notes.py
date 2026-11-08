from __future__ import annotations

import textwrap
import unittest

from framework.tools import check_release_notes


class ReleaseNotesTests(unittest.TestCase):
    def test_current_release_notes_are_valid(self) -> None:
        self.assertEqual(check_release_notes.validate(), [])

    def test_governed_change_requires_changelog_update(self) -> None:
        entries = check_release_notes.parse_changelog(
            textwrap.dedent(
                """
            ## 0.4.0 - 2026-04-30
            ### Compatibility Impact
            No migration required.
            ### Added
            None.
            ### Changed
            Updated docs.
            ### Fixed
            None.
            ### Migration Notes
            No workspace migration required.
            """
            )
        )

        errors = check_release_notes.validate_changed_files(
            ["framework/docs/overview.md"],
            check_release_notes.Version(0, 4, 0),
            entries,
            None,
        )

        self.assertIn("CHANGELOG.md was not updated", "\n".join(errors))

    def test_patch_release_rejects_contract_changes(self) -> None:
        entries = check_release_notes.parse_changelog(
            textwrap.dedent(
                """
            ## 0.4.1 - 2026-05-01
            ### Compatibility Impact
            No migration required.
            ### Added
            None.
            ### Changed
            None.
            ### Fixed
            Fixed validator wording.
            ### Migration Notes
            No workspace migration required.
            """
            )
        )

        errors = check_release_notes.validate_changed_files(
            ["framework/schemas/host.schema.yaml", "CHANGELOG.md"],
            check_release_notes.Version(0, 4, 1),
            entries,
            check_release_notes.Version(0, 4, 0),
        )

        self.assertIn("Patch releases must not include", "\n".join(errors))

    def test_unreleased_pr_pattern_accepted_without_version_bump(self) -> None:
        """Governed files + Unreleased entry + no version bump is the correct PR pattern."""
        entries = check_release_notes.parse_changelog(
            textwrap.dedent(
                """
            ## Unreleased
            ### Compatibility Impact
            No migration required.
            ### Added
            None.
            ### Changed
            Updated generated browser layout.
            ### Fixed
            None.
            ### Migration Notes
            No workspace migration required.

            ## 0.4.0 - 2026-04-30
            ### Compatibility Impact
            No migration required.
            ### Added
            None.
            ### Changed
            Updated docs.
            ### Fixed
            None.
            ### Migration Notes
            No workspace migration required.
            """
            )
        )

        errors = check_release_notes.validate_changed_files(
            ["framework/tools/generate_browser.py", "CHANGELOG.md"],
            check_release_notes.Version(0, 4, 0),
            entries,
            check_release_notes.Version(0, 4, 0),
        )

        self.assertEqual(errors, [])

    def test_unreleased_requires_migration_notes(self) -> None:
        """Unreleased entries always require Migration Notes, even for non-contract changes."""
        entries = check_release_notes.parse_changelog(
            textwrap.dedent(
                """
            ## Unreleased
            ### Compatibility Impact
            No migration required.
            ### Added
            None.
            ### Changed
            Updated generated browser layout.
            ### Fixed
            None.

            ## 0.4.0 - 2026-04-30
            ### Compatibility Impact
            No migration required.
            ### Added
            None.
            ### Changed
            Updated docs.
            ### Fixed
            None.
            ### Migration Notes
            No workspace migration required.
            """
            )
        )

        errors = check_release_notes.validate_changed_files(
            ["framework/tools/generate_browser.py", "CHANGELOG.md"],
            check_release_notes.Version(0, 4, 0),
            entries,
            check_release_notes.Version(0, 4, 0),
        )

        self.assertIn("Migration Notes", "\n".join(errors))

    def test_pre_1_0_non_contract_change_requires_patch_bump(self) -> None:
        entries = check_release_notes.parse_changelog(
            textwrap.dedent(
                """
            ## 0.4.1 - 2026-05-01
            ### Compatibility Impact
            No migration required.
            ### Added
            None.
            ### Changed
            Updated generated browser layout.
            ### Fixed
            None.
            ### Migration Notes
            Regenerate browser output.
            """
            )
        )

        errors = check_release_notes.validate_changed_files(
            ["framework/tools/generate_browser.py", "CHANGELOG.md", "draft-framework.yaml"],
            check_release_notes.Version(0, 5, 0),
            entries,
            check_release_notes.Version(0, 4, 0),
        )

        self.assertIn("expected 0.4.1", "\n".join(errors))

    def test_pre_1_0_contract_change_requires_minor_bump(self) -> None:
        entries = check_release_notes.parse_changelog(
            textwrap.dedent(
                """
            ## 0.4.1 - 2026-05-01
            ### Compatibility Impact
            No migration required.
            ### Added
            None.
            ### Changed
            Updated schema contract.
            ### Fixed
            None.
            ### Migration Notes
            Review workspace validation results.
            """
            )
        )

        errors = check_release_notes.validate_changed_files(
            ["framework/schemas/host.schema.yaml", "CHANGELOG.md", "draft-framework.yaml"],
            check_release_notes.Version(0, 4, 1),
            entries,
            check_release_notes.Version(0, 4, 0),
        )

        self.assertIn("expected 0.5.0", "\n".join(errors))

    def test_changelog_update_for_unreleased_change_requires_quality_notes(self) -> None:
        entries = check_release_notes.parse_changelog(
            textwrap.dedent(
                """
            ## Unreleased
            No notes yet.

            ## 0.4.0 - 2026-04-30
            ### Compatibility Impact
            No migration required.
            ### Added
            None.
            ### Changed
            Updated docs.
            ### Fixed
            None.
            ### Migration Notes
            No workspace migration required.
            """
            )
        )

        errors = check_release_notes.validate_changed_files(
            ["framework/docs/overview.md", "CHANGELOG.md"],
            check_release_notes.Version(0, 4, 0),
            entries,
            None,
        )

        self.assertIn("Unreleased needs a meaningful Compatibility Impact", "\n".join(errors))


    def _promotion_entries(self, version: str = "1.3.0") -> dict:
        return check_release_notes.parse_changelog(
            textwrap.dedent(
                f"""
            ## {version} - 2026-11-08
            ### Compatibility Impact
            Contract change.
            ### Added
            Skills.
            ### Changed
            None.
            ### Fixed
            None.
            ### Migration Notes
            Load the skills.
            """
            )
        )

    def test_promotion_commit_may_apply_a_minor_bump_staged_earlier(self) -> None:
        errors = check_release_notes.validate_changed_files(
            ["CHANGELOG.md", "draft-framework.yaml"],
            check_release_notes.Version(1, 3, 0),
            self._promotion_entries(),
            check_release_notes.Version(1, 2, 1),
        )
        self.assertEqual(errors, [])

    def test_promotion_commit_with_the_regenerated_ai_index_is_accepted(self) -> None:
        errors = check_release_notes.validate_changed_files(
            ["CHANGELOG.md", "draft-framework.yaml", "AI_INDEX.md"],
            check_release_notes.Version(1, 3, 0),
            self._promotion_entries(),
            check_release_notes.Version(1, 2, 1),
        )
        self.assertEqual(errors, [])

    def test_promotion_commit_rejects_decreases_and_skipped_versions(self) -> None:
        for new in ((1, 2, 0), (1, 4, 0), (1, 3, 1), (9, 0, 0)):
            with self.subTest(new=new):
                errors = check_release_notes.validate_changed_files(
                    ["CHANGELOG.md", "draft-framework.yaml"],
                    check_release_notes.Version(*new),
                    self._promotion_entries(".".join(map(str, new))),
                    check_release_notes.Version(1, 2, 1),
                )
                self.assertIn("next patch, minor or major", "\n".join(errors))

    def test_promotion_commit_accepts_next_patch_and_next_major(self) -> None:
        for new in ((1, 2, 2), (2, 0, 0)):
            with self.subTest(new=new):
                errors = check_release_notes.validate_changed_files(
                    ["CHANGELOG.md", "draft-framework.yaml"],
                    check_release_notes.Version(*new),
                    self._promotion_entries(".".join(map(str, new))),
                    check_release_notes.Version(1, 2, 1),
                )
                self.assertEqual(errors, [])

    def test_other_files_with_the_manifest_still_need_the_exact_bump(self) -> None:
        errors = check_release_notes.validate_changed_files(
            ["CHANGELOG.md", "draft-framework.yaml", "framework/tools/generate_browser.py"],
            check_release_notes.Version(1, 3, 0),
            self._promotion_entries(),
            check_release_notes.Version(1, 2, 1),
        )
        self.assertIn("expected 1.2.2", "\n".join(errors))

    def test_promotion_shape_with_an_unreleased_entry_is_not_exempt(self) -> None:
        entries = self._promotion_entries()
        entries["Unreleased"] = entries["1.3.0"]
        errors = check_release_notes.validate_changed_files(
            ["CHANGELOG.md", "draft-framework.yaml"],
            check_release_notes.Version(1, 3, 0),
            entries,
            check_release_notes.Version(1, 2, 1),
        )
        self.assertIn("expected 1.2.2", "\n".join(errors))


class DetectBumpTypeTests(unittest.TestCase):
    def test_patch_for_docs_only(self) -> None:
        bump = check_release_notes.detect_bump_type(files=["framework/docs/overview.md", "CHANGELOG.md"])
        self.assertEqual(bump, "patch")

    def test_minor_for_schema_change(self) -> None:
        bump = check_release_notes.detect_bump_type(files=["framework/schemas/host.schema.yaml", "CHANGELOG.md"])
        self.assertEqual(bump, "minor")

    def test_minor_for_requirement_group_change(self) -> None:
        bump = check_release_notes.detect_bump_type(
            files=["framework/configurations/requirement-groups/rg-foo.yaml", "CHANGELOG.md"]
        )
        self.assertEqual(bump, "minor")

    def test_patch_for_template_change(self) -> None:
        bump = check_release_notes.detect_bump_type(files=["templates/workspace/CODEOWNERS.tmpl", "CHANGELOG.md"])
        self.assertEqual(bump, "patch")

    def test_patch_for_empty_file_list(self) -> None:
        bump = check_release_notes.detect_bump_type(files=[])
        self.assertEqual(bump, "patch")


if __name__ == "__main__":
    unittest.main()
