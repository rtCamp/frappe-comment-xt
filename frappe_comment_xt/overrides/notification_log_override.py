import frappe
from frappe.desk.doctype.notification_log.notification_log import NotificationLog
from frappe.utils.data import get_url_to_form


class NotificationLogOverride(NotificationLog):
    def after_insert(self):
        if self.type == "Mention":
            if self.update_comment_link():
                self.save()
        super().after_insert()

    def update_comment_link(self):
        """
        There is no direct link between the comment and the notification log.
        We determine the comment id by using the content of the email and the most recently created comment, as the comment is created before the notification log.

        Returns:
            bool: True if a comment link was found and set, False otherwise
        """
        comments = frappe.get_all(
            "Comment",
            filters={
                "reference_doctype": self.document_type,
                "reference_name": self.document_name,
            },
            fields=["name", "content"],
            order_by="creation desc",
            limit_page_length=5,
        )

        comment_name = None

        for comment in comments:
            if comment.content in self.email_content:
                comment_name = comment.name
                break

        if comment_name:
            self.link = get_url_to_form(self.document_type, self.document_name) + f"#comment-{comment_name}"
            return True
        return False
