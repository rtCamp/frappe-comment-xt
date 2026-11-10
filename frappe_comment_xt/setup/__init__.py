import json
from pathlib import Path

from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

MODULE = "Frappe Comment Xt"


def install() -> None:
    """Apply all Comment XT customisations (idempotent; runs on install and migrate)."""
    install_custom_fields()


def install_custom_fields() -> None:
    """Install / refresh custom fields from custom_fields.json."""
    data_file = Path(__file__).parent / "custom_fields.json"
    custom_fields: dict[str, list[dict]] = json.loads(data_file.read_text())
    # Tag every field with the app's module so /desk/custom-field shows which app owns it.
    for fields in custom_fields.values():
        for field in fields:
            field["module"] = MODULE
    create_custom_fields(custom_fields, update=True)
