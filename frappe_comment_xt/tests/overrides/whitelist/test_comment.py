"""Coverage of the whitelisted comment endpoints: get_all_replies, add_comment_override, update_comment_override, get_comment_visibility."""

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from frappe_comment_xt.helpers.comment import filter_comments_by_visibility
from frappe_comment_xt.overrides.whitelist.comment import (
    add_comment_override,
    get_all_replies,
    get_comment_visibility,
    update_comment_override,
)
from frappe_comment_xt.tests import (
    TEST_TAG,
    TEST_USER,
    TEST_USER_2,
    TEST_USER_3,
    as_user,
    make_test_comment,
    make_test_tag,
    make_test_user,
)


class TestGetAllRepliesVisibility(IntegrationTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        make_test_user(TEST_USER)
        make_test_user(TEST_USER_2)
        make_test_tag()

    def test_reply_tree_applies_visibility_filter(self):
        """get_all_replies excludes replies a non-owner cannot see."""
        parent = make_test_comment(owner=TEST_USER, content="parent")
        public_reply = make_test_comment(
            owner=TEST_USER,
            content="public reply",
            custom_visibility="Visible to everyone",
            custom_reply_to=parent.name,
        )
        private_reply = make_test_comment(
            owner=TEST_USER,
            content="private reply",
            custom_visibility="Visible to only you",
            custom_reply_to=parent.name,
        )

        with as_user(TEST_USER_2):
            replies = get_all_replies("Tag", TEST_TAG)

        reply_names = {r["name"] for replies_list in replies.values() for r in replies_list}
        self.assertIn(public_reply.name, reply_names)
        self.assertNotIn(private_reply.name, reply_names)


class TestGetAllRepliesStructure(IntegrationTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        make_test_user(TEST_USER)
        make_test_user(TEST_USER_2)

    def setUp(self):
        super().setUp()
        # IntegrationTestCase only rolls back at class-level, so each test gets its own Tag to scope get_all_replies() to just this test's comments
        self.tag = make_test_tag(name=f"_Test FCX RepliesStructure {self._testMethodName}").name

    def test_structure_is_dict_keyed_by_parent(self):
        """get_all_replies returns {parent_name: [reply, ...]} grouping replies under their parents."""
        parent1 = make_test_comment(reference_name=self.tag, owner=TEST_USER, content="parent1")
        parent2 = make_test_comment(reference_name=self.tag, owner=TEST_USER, content="parent2")
        reply_a = make_test_comment(
            reference_name=self.tag, owner=TEST_USER, content="r-a", custom_reply_to=parent1.name
        )
        reply_b = make_test_comment(
            reference_name=self.tag, owner=TEST_USER, content="r-b", custom_reply_to=parent1.name
        )
        reply_c = make_test_comment(
            reference_name=self.tag, owner=TEST_USER, content="r-c", custom_reply_to=parent2.name
        )

        result = get_all_replies("Tag", self.tag)

        self.assertEqual(set(result.keys()), {parent1.name, parent2.name})
        self.assertEqual(
            {r["name"] for r in result[parent1.name]},
            {reply_a.name, reply_b.name},
        )
        self.assertEqual(
            [r["name"] for r in result[parent2.name]],
            [reply_c.name],
        )

    def test_replies_ordered_by_creation_desc(self):
        """Replies under a parent are sorted by creation DESC (most recent first)."""
        parent = make_test_comment(reference_name=self.tag, owner=TEST_USER, content="parent")
        reply_a = make_test_comment(reference_name=self.tag, owner=TEST_USER, content="a", custom_reply_to=parent.name)
        reply_b = make_test_comment(reference_name=self.tag, owner=TEST_USER, content="b", custom_reply_to=parent.name)
        reply_c = make_test_comment(reference_name=self.tag, owner=TEST_USER, content="c", custom_reply_to=parent.name)

        # Stamp creation explicitly so the ordering assertion is deterministic
        frappe.db.set_value("Comment", reply_a.name, "creation", "2026-06-01 10:00:00")
        frappe.db.set_value("Comment", reply_b.name, "creation", "2026-06-01 11:00:00")
        frappe.db.set_value("Comment", reply_c.name, "creation", "2026-06-01 12:00:00")

        result = get_all_replies("Tag", self.tag)

        self.assertEqual(
            [r["name"] for r in result[parent.name]],
            [reply_c.name, reply_b.name, reply_a.name],
        )

    def test_reply_visibility_independent_of_parent(self):
        """A public reply to a private parent is still visible to non-owners; the parent's restriction does not propagate."""
        parent = make_test_comment(
            reference_name=self.tag,
            owner=TEST_USER,
            content="private parent",
            custom_visibility="Visible to only you",
        )
        public_reply = make_test_comment(
            reference_name=self.tag,
            owner=TEST_USER,
            content="public reply to private parent",
            custom_visibility="Visible to everyone",
            custom_reply_to=parent.name,
        )

        with as_user(TEST_USER_2):
            result = get_all_replies("Tag", self.tag)

        reply_names = {r["name"] for replies_list in result.values() for r in replies_list}
        self.assertEqual(reply_names, {public_reply.name})

    def test_parents_excluded_from_structure(self):
        """Comments with no custom_reply_to (the parents themselves) do not appear as values in the dict."""
        parent = make_test_comment(reference_name=self.tag, owner=TEST_USER, content="parent")
        reply = make_test_comment(
            reference_name=self.tag, owner=TEST_USER, content="reply", custom_reply_to=parent.name
        )

        result = get_all_replies("Tag", self.tag)

        all_returned_names = {r["name"] for replies_list in result.values() for r in replies_list}
        self.assertEqual(all_returned_names, {reply.name})


class TestUpdateCommentMentionsRevocation(IntegrationTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        make_test_user(TEST_USER)
        make_test_user(TEST_USER_2)
        make_test_tag()

    def test_unmentioning_user_revokes_visibility(self):
        """After update_comment_override rewrites a Visible-to-mentioned comment's content to drop the mention, the previously mentioned user loses read access."""
        mention_html = f'<span class="mention" data-id="{TEST_USER_2}">@user2</span> heads up'
        comment = make_test_comment(
            owner=TEST_USER,
            content=mention_html,
            custom_visibility="Visible to mentioned",
            mentions=[TEST_USER_2],
        )

        # Pre-update: TEST_USER_2 sees the comment
        comments_view = frappe.get_all(
            "Comment",
            filters={"name": comment.name},
            fields=["name", "owner", "custom_visibility"],
        )
        self.assertEqual(
            [c.name for c in filter_comments_by_visibility(comments_view, TEST_USER_2)],
            [comment.name],
        )

        # Owner updates content to remove the mention span entirely
        with as_user(TEST_USER):
            update_comment_override(
                name=comment.name,
                content="never mind",
                custom_visibility="Visible to mentioned",
            )

        # Post-update: TEST_USER_2 no longer sees it
        self.assertEqual(
            filter_comments_by_visibility(comments_view, TEST_USER_2),
            [],
        )


class TestAddCommentThreadNotifications(IntegrationTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        make_test_user(TEST_USER)
        make_test_user(TEST_USER_2)
        make_test_user(TEST_USER_3)
        make_test_tag()

    def _post_reply(self, parent_name, content="reply", visibility="Visible to everyone", as_who=TEST_USER_2):
        """Post a reply via add_comment_override under a given session user; returns the patch mock for enqueue_create_notification."""
        with patch("frappe_comment_xt.overrides.whitelist.comment.enqueue_create_notification") as mock_notify:
            with as_user(as_who):
                add_comment_override(
                    reference_doctype="Tag",
                    reference_name=TEST_TAG,
                    content=content,
                    comment_email=as_who,
                    comment_by=as_who,
                    custom_visibility=visibility,
                    custom_reply_to=parent_name,
                )
        return mock_notify

    def test_notifies_thread_participants(self):
        """A reply to a thread notifies the original commenter and prior repliers."""
        parent = make_test_comment(owner=TEST_USER, content="parent")
        make_test_comment(owner=TEST_USER_3, content="prior reply", custom_reply_to=parent.name)

        mock_notify = self._post_reply(parent.name)

        recipients = set(mock_notify.call_args[0][0])
        self.assertIn(TEST_USER, recipients)
        self.assertIn(TEST_USER_3, recipients)

    def test_replier_excluded_from_recipients(self):
        """The user posting the reply is removed from the recipient list."""
        parent = make_test_comment(owner=TEST_USER, content="parent")
        mock_notify = self._post_reply(parent.name, as_who=TEST_USER_2)

        recipients = set(mock_notify.call_args[0][0])
        self.assertNotIn(TEST_USER_2, recipients)

    def test_users_mentioned_in_reply_excluded_from_recipients(self):
        """Users mentioned in the new reply are not in the thread-participant recipients (they get a separate Mention notification)."""
        parent = make_test_comment(owner=TEST_USER, content="parent")
        make_test_comment(owner=TEST_USER_3, content="prior reply", custom_reply_to=parent.name)

        # Reply mentions TEST_USER_3 inline; they should be removed from thread recipients
        mention_span = f'<span class="mention" data-id="{TEST_USER_3}">@user3</span> heads up'
        mock_notify = self._post_reply(parent.name, content=mention_span)

        recipients = set(mock_notify.call_args[0][0])
        self.assertNotIn(TEST_USER_3, recipients)
        # Original commenter is still notified
        self.assertIn(TEST_USER, recipients)

    def test_private_reply_does_not_notify(self):
        """A Visible-to-only-you reply does not enqueue any thread notification."""
        parent = make_test_comment(owner=TEST_USER, content="parent")
        mock_notify = self._post_reply(parent.name, visibility="Visible to only you")
        mock_notify.assert_not_called()

    def test_mentioned_visibility_reply_does_not_notify(self):
        """A Visible-to-mentioned reply does not enqueue any thread notification."""
        parent = make_test_comment(owner=TEST_USER, content="parent")
        mock_notify = self._post_reply(parent.name, visibility="Visible to mentioned")
        mock_notify.assert_not_called()

    def test_first_level_comment_does_not_notify(self):
        """A top-level comment (no custom_reply_to) does not enqueue any thread notification."""
        with patch("frappe_comment_xt.overrides.whitelist.comment.enqueue_create_notification") as mock_notify:
            with as_user(TEST_USER):
                add_comment_override(
                    reference_doctype="Tag",
                    reference_name=TEST_TAG,
                    content="top-level",
                    comment_email=TEST_USER,
                    comment_by=TEST_USER,
                    custom_visibility="Visible to everyone",
                )
        mock_notify.assert_not_called()

    def test_exception_in_notification_is_logged_and_swallowed(self):
        """If the notification block raises, the error is caught via frappe.log_error and the comment insert still succeeds."""
        parent = make_test_comment(owner=TEST_USER, content="parent")

        with (
            patch(
                "frappe_comment_xt.overrides.whitelist.comment.enqueue_create_notification",
                side_effect=RuntimeError("kaboom"),
            ),
            patch("frappe.log_error") as mock_log_error,
            as_user(TEST_USER_2),
        ):
            comment = add_comment_override(
                reference_doctype="Tag",
                reference_name=TEST_TAG,
                content="reply",
                comment_email=TEST_USER_2,
                comment_by=TEST_USER_2,
                custom_reply_to=parent.name,
            )

        # Comment still inserted despite the exception in the notification block
        self.assertTrue(frappe.db.exists("Comment", comment.name))
        mock_log_error.assert_called()


class TestUpdateCommentOverride(IntegrationTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        make_test_user(TEST_USER)
        make_test_user(TEST_USER_2)
        make_test_tag()

    def test_owner_can_update(self):
        """The comment's owner may update content and visibility."""
        comment = make_test_comment(owner=TEST_USER, content="before")
        with as_user(TEST_USER):
            update_comment_override(
                name=comment.name,
                content="after",
                custom_visibility="Visible to only you",
            )
        updated = frappe.get_doc("Comment", comment.name)
        self.assertEqual(updated.content, "after")
        self.assertEqual(updated.custom_visibility, "Visible to only you")

    def test_administrator_can_update(self):
        """Administrator may update any comment regardless of ownership."""
        comment = make_test_comment(owner=TEST_USER, content="before")
        with as_user("Administrator"):
            update_comment_override(
                name=comment.name,
                content="admin edit",
                custom_visibility="Visible to mentioned",
            )
        updated = frappe.get_doc("Comment", comment.name)
        self.assertEqual(updated.content, "admin edit")
        self.assertEqual(updated.custom_visibility, "Visible to mentioned")

    def test_non_owner_non_admin_cannot_update(self):
        """A user who is neither the comment's owner nor Administrator gets a PermissionError."""
        comment = make_test_comment(owner=TEST_USER, content="mine")
        with as_user(TEST_USER_2), self.assertRaises(frappe.PermissionError):
            update_comment_override(
                name=comment.name,
                content="hijacked",
                custom_visibility="Visible to everyone",
            )
        # Comment content unchanged
        self.assertEqual(frappe.db.get_value("Comment", comment.name, "content"), "mine")

    def test_empty_visibility_returns_none_and_does_not_modify(self):
        """Calling with empty custom_visibility returns None and leaves the comment untouched (short-circuits before any permission or content path)."""
        comment = make_test_comment(owner=TEST_USER, content="before")
        with as_user(TEST_USER):
            result = update_comment_override(
                name=comment.name,
                content="should not apply",
                custom_visibility="",
            )
        self.assertIsNone(result)
        self.assertEqual(frappe.db.get_value("Comment", comment.name, "content"), "before")

    def test_reference_doc_permission_is_rechecked(self):
        """update_comment_override calls check_permission() on the reference doc before applying content changes."""
        comment = make_test_comment(owner=TEST_USER, content="original")

        captured = []
        original_check = frappe.model.document.Document.check_permission

        def capturing(self_doc, *args, **kwargs):
            captured.append((self_doc.doctype, self_doc.name))
            return original_check(self_doc, *args, **kwargs)

        with (
            patch.object(frappe.model.document.Document, "check_permission", capturing),
            as_user(TEST_USER),
        ):
            update_comment_override(
                name=comment.name,
                content="updated",
                custom_visibility="Visible to everyone",
            )

        self.assertIn(("Tag", TEST_TAG), captured)

    def test_mentions_recomputed_from_content(self):
        """custom_mentions is rebuilt from the new content; previously-absent mentions appear and previously-present ones disappear."""
        comment = make_test_comment(owner=TEST_USER, content="no mentions")

        new_content = f'<span class="mention" data-id="{TEST_USER_2}">@user2</span> mentioned now'
        with as_user(TEST_USER):
            update_comment_override(
                name=comment.name,
                content=new_content,
                custom_visibility="Visible to everyone",
            )

        updated = frappe.get_doc("Comment", comment.name)
        self.assertEqual([m.user for m in updated.custom_mentions], [TEST_USER_2])


class TestGetCommentVisibility(IntegrationTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        make_test_user(TEST_USER)
        make_test_user(TEST_USER_2)
        make_test_tag()

    def test_owner_gets_visibility_dict(self):
        """The comment's owner gets {custom_visibility: <value>} for their own comment."""
        comment = make_test_comment(owner=TEST_USER, custom_visibility="Visible to only you")
        with as_user(TEST_USER):
            result = get_comment_visibility(comment.name)
        self.assertEqual(result, {"custom_visibility": "Visible to only you"})

    def test_administrator_gets_visibility_dict(self):
        """Administrator gets {custom_visibility: <value>} for any comment."""
        comment = make_test_comment(owner=TEST_USER, custom_visibility="Visible to mentioned")
        with as_user("Administrator"):
            result = get_comment_visibility(comment.name)
        self.assertEqual(result, {"custom_visibility": "Visible to mentioned"})

    def test_other_user_gets_none(self):
        """Any user other than the owner or Administrator gets None back, regardless of the comment's visibility."""
        comment = make_test_comment(owner=TEST_USER, custom_visibility="Visible to everyone")
        with as_user(TEST_USER_2):
            result = get_comment_visibility(comment.name)
        self.assertIsNone(result)


class TestAddCommentOverride(IntegrationTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        make_test_user(TEST_USER)
        make_test_user(TEST_USER_2)
        make_test_tag()

    def _set_follow_flag(self, user, value):
        """Set User.follow_commented_documents via the doc API so cache is invalidated."""
        doc = frappe.get_doc("User", user)
        doc.follow_commented_documents = value
        doc.save(ignore_permissions=True)

    def test_check_permission_on_reference_doc(self):
        """add_comment_override calls check_permission() on the reference doc before inserting."""
        captured = []
        original_check = frappe.model.document.Document.check_permission

        def capturing(self_doc, *args, **kwargs):
            captured.append((self_doc.doctype, self_doc.name))
            return original_check(self_doc, *args, **kwargs)

        with (
            patch.object(frappe.model.document.Document, "check_permission", capturing),
            as_user(TEST_USER),
        ):
            add_comment_override(
                reference_doctype="Tag",
                reference_name=TEST_TAG,
                content="hi",
                comment_email=TEST_USER,
                comment_by=TEST_USER,
            )

        self.assertIn(("Tag", TEST_TAG), captured)

    def test_custom_visibility_defaults_to_everyone(self):
        """Omitting custom_visibility produces a Comment with custom_visibility = Visible to everyone."""
        with as_user(TEST_USER):
            comment = add_comment_override(
                reference_doctype="Tag",
                reference_name=TEST_TAG,
                content="hi",
                comment_email=TEST_USER,
                comment_by=TEST_USER,
            )
        self.assertEqual(comment.custom_visibility, "Visible to everyone")

    def test_custom_reply_to_defaults_to_none(self):
        """Omitting custom_reply_to produces a Comment with custom_reply_to set to None."""
        with as_user(TEST_USER):
            comment = add_comment_override(
                reference_doctype="Tag",
                reference_name=TEST_TAG,
                content="hi",
                comment_email=TEST_USER,
                comment_by=TEST_USER,
            )
        self.assertIsNone(comment.custom_reply_to)

    def test_mentions_extracted_from_content(self):
        """custom_mentions is populated from mention spans in the content."""
        content = f'<span class="mention" data-id="{TEST_USER_2}">@user2</span> hi'
        with as_user(TEST_USER):
            comment = add_comment_override(
                reference_doctype="Tag",
                reference_name=TEST_TAG,
                content=content,
                comment_email=TEST_USER,
                comment_by=TEST_USER,
            )
        self.assertEqual([m.user for m in comment.custom_mentions], [TEST_USER_2])

    def test_inline_images_extracted_to_files(self):
        """Inline base64 images are extracted to File records and the img src is replaced with the file URL."""
        # 1x1 transparent PNG
        base64_png = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        content_with_image = f'<img src="data:image/png;base64,{base64_png}" alt="x"/>'

        with as_user(TEST_USER):
            comment = add_comment_override(
                reference_doctype="Tag",
                reference_name=TEST_TAG,
                content=content_with_image,
                comment_email=TEST_USER,
                comment_by=TEST_USER,
            )

        self.assertNotIn("data:image/png;base64", comment.content)
        self.assertIn("/files/", comment.content)

    def test_follow_commented_documents_on_triggers_follow(self):
        """When the session user has follow_commented_documents=1, follow_document is invoked with the reference doc."""
        self._set_follow_flag(TEST_USER, 1)

        with (
            patch("frappe_comment_xt.overrides.whitelist.comment.follow_document") as mock_follow,
            as_user(TEST_USER),
        ):
            add_comment_override(
                reference_doctype="Tag",
                reference_name=TEST_TAG,
                content="hi",
                comment_email=TEST_USER,
                comment_by=TEST_USER,
            )

        mock_follow.assert_called_once_with("Tag", TEST_TAG, TEST_USER)

    def test_follow_commented_documents_off_does_not_follow(self):
        """When the session user has follow_commented_documents=0, follow_document is not called."""
        self._set_follow_flag(TEST_USER, 0)

        with (
            patch("frappe_comment_xt.overrides.whitelist.comment.follow_document") as mock_follow,
            as_user(TEST_USER),
        ):
            add_comment_override(
                reference_doctype="Tag",
                reference_name=TEST_TAG,
                content="hi",
                comment_email=TEST_USER,
                comment_by=TEST_USER,
            )

        mock_follow.assert_not_called()

    def test_returns_inserted_comment_doc(self):
        """The function returns the inserted Comment document, which exists in the DB and carries the supplied content."""
        with as_user(TEST_USER):
            result = add_comment_override(
                reference_doctype="Tag",
                reference_name=TEST_TAG,
                content="hello world",
                comment_email=TEST_USER,
                comment_by=TEST_USER,
            )

        self.assertEqual(result.doctype, "Comment")
        self.assertTrue(frappe.db.exists("Comment", result.name))
        self.assertEqual(result.content, "hello world")
