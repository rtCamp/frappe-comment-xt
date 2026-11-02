_patched = False


def patch():
    """Replace Frappe's docinfo comment loader once per process.

    Outside developer mode frappe caches hooks in redis, so hooks.py is imported only by the
    process that fills the cache. Running this from before_request / before_job reaches every
    web and worker process. The replacement itself checks per call whether this app is installed
    on the current site, so patching is safe on a shared bench.
    """
    global _patched
    if _patched:
        return
    # set first so a failure is logged once per process, not on every request
    _patched = True
    try:
        _apply()
    except Exception:
        import frappe

        frappe.log_error(title="Monkey Patching Error")


def _apply():
    import frappe.desk.form.load as frappe_load

    from frappe_comment_xt.helpers import comment as helper

    # captured at patch time, not import time, so another app patching the same function first is still reached;
    # never capture ourselves (re-patching in tests) or the fallback would recurse
    if frappe_load.add_comments is not helper.add_comments_in_timeline:
        helper.core_add_comments = frappe_load.add_comments
    frappe_load.add_comments = helper.add_comments_in_timeline

    # activity.py (Frappe >= 16.51) binds add_comments by name at import, so load.add_comments alone misses it
    try:
        import frappe.desk.form.activity as frappe_activity
    except ImportError:
        return
    frappe_activity.add_comments = helper.add_comments_in_timeline
