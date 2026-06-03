# Copyright (c) 2026, rtCamp and Contributors
# See license.txt
"""Mention-type Notification Log linkback to the originating comment.

Tests call update_comment_link / after_insert directly on an unsaved doc instead of going through .insert(). This avoids interference from other apps' before_save hooks on Notification Log (e.g. next_crm rewrites `#comment-(\\w+)` -> `#comments` on save, which would silently undo our anchor).
"""

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from frappe_comment_xt.tests import (
    TEST_USER,
    make_test_comment,
    make_test_tag,
    make_test_user,
)


class TestUpdateCommentLink(IntegrationTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        make_test_user(TEST_USER)

    def setUp(self):
        super().setUp()
        # Each test gets its own Tag so the "latest 5 comments" lookup is scoped to just this test's comments
        self.tag = make_test_tag(name=f"_Test FCX NotifLog {self._testMethodName}").name

    def _new_log(self, ntype, email_content, link=None):
        log = frappe.new_doc("Notification Log")
        log.type = ntype
        log.document_type = "Tag"
        log.document_name = self.tag
        log.subject = "test"
        log.email_content = email_content
        log.from_user = "Administrator"
        log.for_user = TEST_USER
        if link is not None:
            log.link = link
        return log

    def test_link_anchored_to_matching_comment(self):
        """update_comment_link sets link to <form-url>#comment-<name> and returns True when a comment's content is a substring of email_content."""
        comment = make_test_comment(
            reference_name=self.tag,
            owner=TEST_USER,
            content="distinctive payload abc123",
        )
        log = self._new_log("Mention", "the latest update: distinctive payload abc123 - check it out")

        self.assertTrue(log.update_comment_link())
        self.assertTrue(log.link.endswith(f"#comment-{comment.name}"))

    def test_link_unchanged_when_no_match(self):
        """update_comment_link returns False and leaves link untouched when no comment matches."""
        make_test_comment(reference_name=self.tag, owner=TEST_USER, content="this is one comment")
        log = self._new_log("Mention", "totally unrelated payload xyz", link="/sentinel")

        self.assertFalse(log.update_comment_link())
        self.assertEqual(log.link, "/sentinel")

    def test_after_insert_skips_update_for_non_mention_types(self):
        """For non-Mention notification logs, after_insert does not invoke update_comment_link."""
        log = self._new_log("Alert", "anything")

        with (
            patch.object(log, "update_comment_link") as mock_update,
            patch("frappe.desk.doctype.notification_log.notification_log.NotificationLog.after_insert"),
        ):
            log.after_insert()

        mock_update.assert_not_called()
