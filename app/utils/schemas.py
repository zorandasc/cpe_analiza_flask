from app.extensions import db
from app.models import CpeTypes


# SINGLE SOURCE OF TRUTH FOR WHOLE CPE-RECORDS AND CPE-DISMANTLE TABLE
# THIS IS LIST OF FULL CPE_TYPE OBJECTS, BUT ONLY IF is_active
# FROM THIS SCHEMA LIST:
# 1. WE USE IT TO BUILD RAW DYNAMIC PIVOT SQL QUERY
# 2. WE ALSO USE IT IN HTML TABLES TEMPLATES DISPLAY
def get_cpe_types_column_schema(column_name: str = "is_visible_in_total"):
    filter_column = getattr(CpeTypes, column_name)

    cpe_types = (
        db.session.query(CpeTypes)
        .filter(filter_column)
        .order_by(CpeTypes.display_order.nullslast(), CpeTypes.id)
        .all()
    )

    # Prepare the structured list and separate lists
    schema_list = [
        {
            "id": ct.id,
            "name": ct.name,
            "label": ct.label,
            "cpe_type": ct.type,
            "has_remote": ct.has_remote,
            "has_adapter": ct.has_adapter,
            "header_color": ct.header_color,
            "display_order": ct.display_order,
        }
        for ct in cpe_types
    ]

    return schema_list
