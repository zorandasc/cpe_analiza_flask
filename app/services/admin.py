from sqlalchemy import text
from app.extensions import db
from app.models import CpeTypes


def update_cpe_type(cpe_id, data):
    cpe = CpeTypes.query.get_or_404(cpe_id)

    # 1. Logic: Name Uniqueness check
    existing = CpeTypes.query.filter(
        CpeTypes.name == data["name"], CpeTypes.id != cpe_id
    ).first()
    if existing:
        return False, "Tip CPE opreme već postoji!"

    # Handle Reordering for Total
    # 1. from user
    new_total_order = int(data["order_total"]) if data["order_total"] else None

    # 2. from db
    old_total_order = cpe.order_in_total

    # 3. recalculate other
    handle_display_order("order_in_total", cpe.id, old_total_order, new_total_order)

    # 4. update
    cpe.order_in_total = new_total_order

    # Handle Reordering for Dismantle
    new_dismantle_order = (
        int(data["order_dismantle"]) if data["order_dismantle"] else None
    )

    old_dismantle_order = cpe.order_in_dismantle

    handle_display_order(
        "order_in_dismantle", cpe.id, old_dismantle_order, new_dismantle_order
    )

    cpe.order_in_dismantle = new_dismantle_order

    # Handle Reordering for broken
    # 1. from user
    new_broken_order = int(data["order_broken"]) if data["order_broken"] else None

    # 2. from db
    old_broken_order = cpe.order_in_broken

    # 3. recalculate others
    handle_display_order("order_in_broken", cpe.id, old_broken_order, new_broken_order)

    # 4. update
    cpe.order_in_broken = new_broken_order

    # Update other CPETYPE fields
    cpe.name = data["name"]
    cpe.label = data["label"]
    cpe.type = data["type"]
    cpe.header_color = data.get("header_color") or None
    cpe.has_remote = data.get("has_remote", False)
    cpe.has_adapter = data.get("has_adapter", False)
    cpe.visible_in_total = data.get("visible_in_total", False)
    cpe.visible_in_dismantle = data.get("visible_in_dismantle", False)
    cpe.visible_in_broken = data.get("visible_in_broken", False)

    try:
        db.session.commit()
        return True, "Cpe tip uspješno izmijenjen!"
    except Exception as e:
        db.session.rollback()
        return False, str(e)


def handle_display_order(column_name, cpe_id, old_order, new_order):
    """
    Reorders CPE type.

    column_name: 'order_in_total', 'order_in_dismantle', 'order_in_broken

    Rules:
    - None -> number  : insert at position
    - number -> number: move within ordering
    """

    # Safety
    if new_order < 1:
        raise ValueError("display_order must be >= 1")

    # ----------------------------------
    # No change
    # ----------------------------------
    if new_order == old_order:
        return

    # ----------------------------------
    # First placement (None -> number)
    # ----------------------------------
    if old_order is None:
        db.session.execute(
            text(f"""
                UPDATE cpe_types
                SET {column_name} = {column_name} + 1
                WHERE {column_name} >= :new
            """),
            {"new": new_order},
        )
        return
    # ----------------------------------
    # Reordering
    # ----------------------------------
    if new_order < old_order:
        # moving UP
        db.session.execute(
            text(f"""
                UPDATE cpe_types
                SET {column_name} = {column_name} + 1
                WHERE {column_name} >= :new
                  AND {column_name} < :old
                  AND id != :id
            """),
            {"new": new_order, "old": old_order, "id": cpe_id},
        )

    else:
        # moving DOWN
        db.session.execute(
            text(f"""
                UPDATE cpe_types
                SET {column_name} = {column_name} - 1
                WHERE {column_name} > :old
                  AND {column_name} <= :new
                  AND id != :id
            """),
            {"new": new_order, "old": old_order, "id": cpe_id},
        )
