# Copyright (c) 2026, rtCamp and Contributors
# See license.txt
"""Visibility filtering in get_all_replies, and the un-mention revocation path through update_comment_override."""

import frappe
from frappe.tests import IntegrationTestCase

from frappe_comment_xt.helpers.comment import filter_comments_by_visibility
from frappe_comment_xt.overrides.whitelist.comment import (
    get_all_replies,
    update_comment_override,
)
from frappe_comment_xt.tests import (
    TEST_TAG,
    TEST_USER,
    TEST_USER_2,
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
