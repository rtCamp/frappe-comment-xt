from frappe_comment_xt.setup import install


def after_install() -> None:
    """Create the app's custom fields when it is installed on a site."""
    install()
