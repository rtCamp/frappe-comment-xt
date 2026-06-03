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
