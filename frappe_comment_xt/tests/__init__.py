"""
Setup and helpers for FCX test suite.
"""

import contextlib

import frappe

TEST_USER = "_test_fcx_user1@example.com"
TEST_USER_2 = "_test_fcx_user2@example.com"
TEST_USER_3 = "_test_fcx_user3@example.com"
TEST_TAG = "_Test FCX Tag"


def ensure_doc(doctype, name, **fields):
    """
    Return the existing doc with this name, or insert one and return it.
    Caller is responsible for picking a doctype whose autoname respects the supplied name.
    """
    if frappe.db.exists(doctype, name):
        return frappe.get_doc(doctype, name)
    return frappe.get_doc({"doctype": doctype, "name": name, **fields}).insert(ignore_permissions=True)


def make_test_user(email):
    """Create a User with no welcome email."""
    return ensure_doc(
        "User",
        email,
        email=email,
        first_name=email.split("@")[0],
        send_welcome_email=0,
    )


def make_test_tag(name=TEST_TAG):
    """
    Create a Tag to attach comments to.
    Tag is autoname=Prompt so the supplied name sticks, and it's readable by the All role so test users can pass reference permission checks.
    """
    return ensure_doc("Tag", name)


def make_test_comment(
    reference_doctype="Tag",
    reference_name=TEST_TAG,
    owner=None,
    content="Test comment",
    comment_type="Comment",
    custom_visibility="Visible to everyone",
    custom_reply_to=None,
    mentions=None,
):
    """
    Insert a Comment.
    If owner is set, frappe.session.user is switched for the duration of insert so owner+comment_email match.
    """
    target_user = owner or frappe.session.user
    data = {
        "doctype": "Comment",
        "comment_type": comment_type,
        "reference_doctype": reference_doctype,
        "reference_name": reference_name,
        "comment_email": target_user,
        "comment_by": target_user,
        "content": content,
        "custom_visibility": custom_visibility,
        "custom_reply_to": custom_reply_to,
        "custom_mentions": [{"user": u} for u in (mentions or [])],
    }
    with as_user(target_user):
        return frappe.get_doc(data).insert(ignore_permissions=True)


@contextlib.contextmanager
def as_user(email):
    """
    Temporarily switch frappe.session.user for the duration of the block.
    """
    original = frappe.session.user
    frappe.set_user(email)
    try:
        yield
    finally:
        frappe.set_user(original)
