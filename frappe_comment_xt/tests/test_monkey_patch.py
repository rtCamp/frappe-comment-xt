"""monkey_patch.patch() wiring: both docinfo loaders are replaced, the patch is idempotent, and
the replacement falls back to core on a site without this app. Plus the end-to-end check through
the two whitelisted entry points a non-owner actually hits."""

import sys
from unittest.mock import patch as mock_patch

import frappe
import frappe.desk.form.activity as frappe_activity
import frappe.desk.form.load as frappe_load
from frappe.tests import IntegrationTestCase

from frappe_comment_xt import monkey_patch
from frappe_comment_xt.helpers import comment as helper
from frappe_comment_xt.tests import (
    TEST_TAG,
    TEST_USER,
    TEST_USER_2,
    as_user,
    make_test_comment,
    make_test_tag,
    make_test_user,
)


class TestMonkeyPatch(IntegrationTestCase):
    def test_patch_replaces_both_loaders_once(self):
        """patch() rebinds load.add_comments and activity.add_comments; a second call is a no-op."""
        monkey_patch._patched = False
        monkey_patch.patch()
        self.assertIs(frappe_load.add_comments, helper.add_comments_in_timeline)
        self.assertIs(frappe_activity.add_comments, helper.add_comments_in_timeline)

        sentinel = object()
        with mock_patch.object(frappe_load, "add_comments", sentinel):
            monkey_patch.patch()
            self.assertIs(frappe_load.add_comments, sentinel)

    def test_repatch_never_captures_itself_as_fallback(self):
        """Re-running the patch must keep the real core loader as fallback, or the fallback path would recurse."""
        monkey_patch._patched = False
        monkey_patch.patch()
        self.assertIsNot(helper.core_add_comments, helper.add_comments_in_timeline)

    def test_load_patched_without_activity_module(self):
        """Frappe below 16.51 has no activity module; the load patch must still land."""
        monkey_patch._patched = False
        with (
            mock_patch.dict(sys.modules, {"frappe.desk.form.activity": None}),
            mock_patch.object(frappe_load, "add_comments", frappe_load.add_comments),
        ):
            monkey_patch.patch()
            self.assertIs(frappe_load.add_comments, helper.add_comments_in_timeline)

    def test_hooks_register_patch(self):
        for hook in ("before_request", "before_job"):
            self.assertIn("frappe_comment_xt.monkey_patch.patch", frappe.get_hooks(hook))

    def test_falls_back_to_core_when_app_not_installed(self):
        """The patch is process-wide; a site without the app must get core behaviour per call."""
        doc = frappe._dict(doctype="Tag", name=TEST_TAG)
        with (
            mock_patch.object(helper.frappe, "get_installed_apps", return_value=["frappe"]),
            mock_patch.object(helper, "core_add_comments") as core,
        ):
            helper.add_comments_in_timeline(doc, frappe._dict())
        core.assert_called_once()


class TestDocinfoEntryPoints(IntegrationTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        make_test_user(TEST_USER)
        make_test_user(TEST_USER_2)
        make_test_tag()
        monkey_patch._patched = False
        monkey_patch.patch()

    def test_private_comment_hidden_from_non_owner_in_docinfo_and_activity(self):
        """The paths the desk really calls, not the helper directly: get_docinfo and get_activity_timeline."""
        private = make_test_comment(owner=TEST_USER, custom_visibility="Visible to only you")
        doc = frappe.get_doc("Tag", TEST_TAG)

        # other apps' additional_timeline_content hooks are not under test and may need extra perms
        with (
            as_user(TEST_USER_2),
            mock_patch.object(frappe_load, "get_additional_timeline_content", return_value=[]),
        ):
            frappe_load.get_docinfo(doc)
            docinfo_names = {c.name for c in frappe.response["docinfo"].comments}
            activity = frappe_activity.get_activity_timeline("Tag", TEST_TAG)
        activity_keys = {a["key"] for a in activity["activities"]}

        self.assertNotIn(private.name, docinfo_names)
        self.assertNotIn(f"comment:{private.name}", activity_keys)
