def patch_add_comments_in_timeline():
    import frappe.desk.form.load as frappe_load
    from frappe import get_installed_apps

    from frappe_comment_xt.helpers.comment import add_comments_in_timeline

    # in shared bench this is required so it won't break other apps that use add_comments in their codebase.
    # This is a safe check as the patch will only be applied if the app is installed in the site.
    if "frappe_comment_xt" not in get_installed_apps():
        return
    # A monkey patch was written for this function as it is used in many places within Frappe. Care was taken to avoid breaking existing code.
    try:
        frappe_load.add_comments = add_comments_in_timeline
    except Exception:
        pass


def patch():
    patch_add_comments_in_timeline()
