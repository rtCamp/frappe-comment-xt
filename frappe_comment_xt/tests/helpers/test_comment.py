# Copyright (c) 2026, rtCamp and Contributors
# See license.txt
"""Visibility-mode coverage of filter_comments_by_visibility plus the timeline integration path through add_comments_in_timeline."""

import frappe
from frappe.tests import IntegrationTestCase

from frappe_comment_xt.helpers.comment import (
    add_comments_in_timeline,
    filter_comments_by_visibility,
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


def _fetch(names):
    """Return the {name, owner, custom_visibility} shape that filter_comments_by_visibility consumes."""
    return frappe.get_all(
        "Comment",
        filters={"name": ["in", names]},
        fields=["name", "owner", "custom_visibility"],
    )


class TestFilterCommentsByVisibility(IntegrationTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        make_test_user(TEST_USER)
        make_test_user(TEST_USER_2)
        make_test_user(TEST_USER_3)
        make_test_tag()

    def test_unset_visibility_is_treated_as_everyone(self):
        """A comment inserted without custom_visibility is visible to non-owners."""
        raw = frappe.get_doc(
            {
                "doctype": "Comment",
                "comment_type": "Comment",
                "reference_doctype": "Tag",
                "reference_name": TEST_TAG,
                "comment_email": TEST_USER,
                "comment_by": TEST_USER,
                "content": "default visibility",
            }
        ).insert(ignore_permissions=True)

        result = filter_comments_by_visibility(_fetch([raw.name]), TEST_USER_2)
        self.assertEqual([c.name for c in result], [raw.name])

    def test_visible_to_only_you_hidden_from_non_owner(self):
        """Non-owner cannot see a private comment."""
        private = make_test_comment(owner=TEST_USER, custom_visibility="Visible to only you")
        self.assertEqual(filter_comments_by_visibility(_fetch([private.name]), TEST_USER_2), [])

    def test_visible_to_only_you_visible_to_owner(self):
        """Owner can see their own private comment."""
        private = make_test_comment(owner=TEST_USER, custom_visibility="Visible to only you")
        result = filter_comments_by_visibility(_fetch([private.name]), TEST_USER)
        self.assertEqual([c.name for c in result], [private.name])

    def test_visible_to_mentioned_visible_to_owner(self):
        """Owner of a 'Visible to mentioned' comment can see it."""
        c = make_test_comment(
            owner=TEST_USER,
            custom_visibility="Visible to mentioned",
            mentions=[TEST_USER_2],
        )
        result = filter_comments_by_visibility(_fetch([c.name]), TEST_USER)
        self.assertEqual([cc.name for cc in result], [c.name])

    def test_visible_to_mentioned_visible_to_mentioned_user(self):
        """A mentioned user can see a 'Visible to mentioned' comment."""
        c = make_test_comment(
            owner=TEST_USER,
            custom_visibility="Visible to mentioned",
            mentions=[TEST_USER_2],
        )
        result = filter_comments_by_visibility(_fetch([c.name]), TEST_USER_2)
        self.assertEqual([cc.name for cc in result], [c.name])

    def test_visible_to_mentioned_hidden_from_non_mentioned_non_owner(self):
        """A user who is neither owner nor mentioned cannot see a 'Visible to mentioned' comment."""
        c = make_test_comment(
            owner=TEST_USER,
            custom_visibility="Visible to mentioned",
            mentions=[TEST_USER_2],
        )
        self.assertEqual(filter_comments_by_visibility(_fetch([c.name]), TEST_USER_3), [])

    def test_administrator_sees_all_visibility_levels(self):
        """Administrator bypasses every visibility filter."""
        private = make_test_comment(owner=TEST_USER, custom_visibility="Visible to only you")
        mentioned = make_test_comment(
            owner=TEST_USER,
            custom_visibility="Visible to mentioned",
            mentions=[TEST_USER_2],
        )
        public = make_test_comment(owner=TEST_USER, custom_visibility="Visible to everyone")

        result = filter_comments_by_visibility(
            _fetch([private.name, mentioned.name, public.name]),
            "Administrator",
        )
        self.assertEqual(
            {c.name for c in result},
            {private.name, mentioned.name, public.name},
        )


class TestAddCommentsInTimelineVisibility(IntegrationTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        make_test_user(TEST_USER)
        make_test_user(TEST_USER_2)
        make_test_tag()

    def test_timeline_applies_visibility_filter(self):
        """add_comments_in_timeline routes comments through filter_comments_by_visibility, so a private comment is excluded for non-owners."""
        public = make_test_comment(
            owner=TEST_USER,
            content="public content",
            custom_visibility="Visible to everyone",
        )
        private = make_test_comment(
            owner=TEST_USER,
            content="private content",
            custom_visibility="Visible to only you",
        )

        doc = frappe._dict(doctype="Tag", name=TEST_TAG)
        docinfo = frappe._dict()
        with as_user(TEST_USER_2):
            add_comments_in_timeline(doc, docinfo)

        timeline_names = {c.name for c in docinfo.comments}
        self.assertIn(public.name, timeline_names)
        self.assertNotIn(private.name, timeline_names)


class TestAddCommentsInTimelineReplyFilter(IntegrationTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        make_test_user(TEST_USER)
        make_test_tag()

    def test_timeline_excludes_replies(self):
        """add_comments_in_timeline returns only top-level comments; entries with a custom_reply_to are not included."""
        parent = make_test_comment(owner=TEST_USER, content="top-level")
        reply = make_test_comment(
            owner=TEST_USER,
            content="reply",
            custom_reply_to=parent.name,
        )

        doc = frappe._dict(doctype="Tag", name=TEST_TAG)
        docinfo = frappe._dict()
        add_comments_in_timeline(doc, docinfo)

        timeline_names = {c.name for c in docinfo.comments}
        self.assertIn(parent.name, timeline_names)
        self.assertNotIn(reply.name, timeline_names)
