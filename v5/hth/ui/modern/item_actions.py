"""Things you do *to an item* in the new layout: new item, edit (with unit conversion),
category, stock movements, delete.  The same service calls as the classic Items screen."""

from __future__ import annotations

from hth.domain.constants import ITEM_TYPES, PAKKA_KACHA, UNITS
from hth.domain.models import Item
from hth.domain.units import normalize
from hth.services.accounts import ValidationError
from hth.ui.format import today_str
from hth.ui.modern.actions import _lines
from hth.ui.widgets.dialogs import Field, confirm, run_form

TYPE_NAMES = {"F": "Fertiliser", "P": "Pesticide", "S": "Seed", "C": "Crop", "O": "Other"}


def new_item(parent, ctx) -> Item | None:
    fields = [
        Field("name", "Item name"),
        Field("unit", "Stock unit  (KG / LTR can be sold loose)", "option", "BAG", UNITS),
        Field("opening", "Opening quantity", default="0"),
        Field("stock_value", "Cost per unit", default="0"),
        Field("last_value", "Sale price per unit", default="0"),
        Field("item_type", "Type  F fertiliser · P pesticide · S seed · C crop · O other", "option", "O", ITEM_TYPES),
        Field("gst", "GST %", default="0"),
        Field("batch", "Batch", default="NA"),
        Field("expiry", "Expiry  (YYYY-MM-DD or NA)", default="NA"),
        Field("pk", "Pakka / Kacha", "option", "P", PAKKA_KACHA),
        Field("source", "Bought from (optional)"),
    ]
    made: dict = {}

    def submit(v: dict) -> None:
        made["i"] = ctx.inventory.add_item(
            v["name"],
            v["stock_value"] or 0,
            v["last_value"] or 0,
            v["unit"],
            v["batch"] or "NA",
            v["expiry"] or "NA",
            v["gst"] or 0,
            v["item_type"],
            v["pk"],
            today_str(),
            v["opening"] or 0,
            v["source"],
            ctx.username,
        )

    if run_form(parent, "New item", fields, submit, "Create") and made:
        item = made["i"]
        ctx.toast(f"Item #{item.id} {item.name} added", "success")
        return item
    return None


def edit_item(parent, ctx, item_id: int) -> bool:
    i = ctx.inventory.get_item(item_id)
    if i is None:
        return False
    fields = [
        Field("name", "Name", default=i.name),
        Field("stock_value", "Stock value (cost) per unit", default=f"{i.stock_value:g}"),
        Field("last_value", "Last price per unit", default=f"{i.last_value:g}"),
        Field("unit", "Unit  (changing it converts the whole history)", "option", normalize(i.unit) or "PCS", UNITS),
        Field("batch", "Batch", default=i.batch),
        Field("expiry_date", "Expiry", default=i.expiry_date),
        Field("gst_rate", "GST %", default=f"{i.gst_rate:g}"),
        Field("item_type", "Type", "option", i.item_type, ITEM_TYPES),
        Field("pakka_kacha", "Pakka/Kacha", "option", i.pakka_kacha, PAKKA_KACHA),
        Field("name_hi", "Name in Hindi  (blank = automatic)", default=i.name_hi if i.hi_manual else ""),
    ]

    def submit(v: dict) -> None:
        ctx.inventory.update_item(i.id, ctx.username, **{k: x for k, x in v.items() if k not in ("unit", "name_hi")})
        if v["name_hi"]:
            ctx.hindi.set_item(i.id, v["name_hi"], ctx.username)
        elif i.hi_manual:
            ctx.hindi.reset("item", i.id, ctx.username)

    values = run_form(parent, f"Edit item #{i.id}", fields, submit)
    if not values:
        return False
    ctx.app.refresh_names()
    if normalize(values["unit"]) != normalize(i.unit):
        change_unit(parent, ctx, i.id, normalize(values["unit"]))
    return True


def change_unit(parent, ctx, item_id: int, new_unit: str) -> None:
    i = ctx.inventory.get_item(item_id)
    old_unit = normalize(i.unit)
    factor = ctx.inventory.conversion_factor(i.id, new_unit)
    if factor is not None:
        if not confirm(
            parent,
            "Convert unit",
            _lines(
                f"Change {i.name} from {old_unit} to {new_unit}?",
                "",
                f"1 {old_unit} = {factor:g} {new_unit}. Every movement, lot and rate will be converted;",
                "money amounts stay the same.",
            ),
        ):
            return
    else:
        result = run_form(
            parent,
            f"{old_unit} → {new_unit}",
            [Field("factor", f"How many {new_unit} is 1 {old_unit}?  (blank = relabel only, no conversion)")],
            lambda v: None,
            "Continue",
        )
        if result is None:
            return
        text = result["factor"].strip()
        if not text:
            ctx.inventory.update_item(i.id, ctx.username, unit=new_unit)
            ctx.toast(f"Unit relabelled to {new_unit}; history not converted", "warning")
            return
        try:
            factor = float(text)
        except ValueError:
            ctx.toast("Factor must be a number", "error")
            return
    try:
        used = ctx.inventory.change_unit(i.id, new_unit, ctx.username, factor)
    except ValidationError as exc:
        ctx.toast(str(exc), "error")
        return
    ctx.toast(f"{i.name}: {old_unit} → {new_unit} (x{used:g}), history converted", "success")


def set_category(parent, ctx, item_id: int) -> bool:
    i = ctx.inventory.get_item(item_id)
    if i is None:
        return False
    fields = [
        Field(
            "category", "Category (E = discontinued, kept out of stock reports)", "option", i.category, list("ABCDE")
        ),
        Field("mode", "After saving", "option", "Keep (locked)", ["Keep (locked)", "Let auto-categorise change it"]),
    ]

    def submit(v: dict) -> None:
        ctx.inventory.set_category(i.id, v["category"], ctx.username, locked=v["mode"].startswith("Keep"))

    if run_form(parent, f"Category of {i.name}", fields, submit):
        ctx.toast("Category updated", "success")
        return True
    return False


def delete_item(parent, ctx, item_id: int) -> bool:
    i = ctx.inventory.get_item(item_id)
    if i is None or not confirm(parent, "Delete item", _lines(f"Delete #{i.id} {i.name} and all its movements?")):
        return False
    try:
        ctx.inventory.delete_item(i.id, ctx.username)
    except ValidationError as exc:
        ctx.toast(str(exc), "error")
        return False
    ctx.toast("Item deleted", "success")
    return True


def add_movement(parent, ctx, item_id: int) -> bool:
    fields = [
        Field("date", "Date", default=today_str()),
        Field("received", "Received", default="0"),
        Field("sale", "Sold / taken out", default="0"),
        Field("description", "Description"),
        Field("tags", "Tags"),
    ]
    return bool(
        run_form(
            parent,
            "Add stock movement",
            fields,
            lambda v: ctx.inventory.add_item_transaction(
                item_id, v["date"], v["received"], v["sale"], v["description"], v["tags"], ctx.username
            ),
        )
    )


def edit_movement(parent, ctx, movement_id: int) -> bool:
    t = ctx.inventory.get_item_transaction(movement_id)
    if t is None:
        return False
    fields = [
        Field("date", "Date", default=t.date),
        Field("received", "Received", default=f"{t.received:g}"),
        Field("sale", "Sold / taken out", default=f"{t.sale:g}"),
        Field("description", "Description", default=t.description),
        Field("tags", "Tags", default=t.tags),
    ]
    return bool(
        run_form(
            parent,
            f"Edit movement #{t.id}",
            fields,
            lambda v: ctx.inventory.update_item_transaction(
                t.id, v["date"], v["received"], v["sale"], v["description"], v["tags"], ctx.username
            ),
        )
    )


def delete_movement(parent, ctx, movement_id: int) -> bool:
    t = ctx.inventory.get_item_transaction(movement_id)
    if t is None:
        return False
    if not confirm(
        parent,
        "Delete movement",
        _lines(
            f"Delete movement #{t.id} ({t.date}, +{t.received:g} / -{t.sale:g})?",
            "The khata entry it came from is not changed.",
        ),
    ):
        return False
    ctx.inventory.delete_item_transaction(t.id, ctx.username)
    ctx.toast("Movement deleted", "success")
    return True
