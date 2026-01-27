from typing import Optional
import datetime
from app.extensions import db
from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKeyConstraint,
    Integer,
    PrimaryKeyConstraint,
    String,
    Text,
    UniqueConstraint,
    CheckConstraint,
    text,
    Enum,
    ForeignKey,
    DDL,
    event,
    Time,
    func
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum
from flask_login import UserMixin


# To make this robust, define the Enum so that the Value (what goes in the DB)
# s explicitly the string with the space, while the Name
# (how you use it in code) uses an underscore.
class CpeTypeEnum(str, enum.Enum):
    IAD = "IAD"
    ONT = "ONT"
    STB = "STB"
    ANTENA = "ANTENA"
    ROUTER = "ROUTER"
    SWITCH = "SWITCH"
    # Name is WIFI_EXTENDER, but Value is "WIFI EXTENDER"
    WIFI_EXTENDER = "WIFI_EXTENDER"
    WIFI_ACCESS_POINT = "WIFI_ACCESS_POINT"
    PHONES = "PHONES"
    SERVER = "SERVER"
    PC = "PC"
    IOT = "IOT"
    STB_DTH = "STB_DTH"
    LNB = "LNB"
    OTHER = "OTHER"

    def __str__(self):
        return self.value


# This is a "pro-tip" for SQLAlchemy. By inheriting from str,
# your Enum behaves like a string, which makes it much more
# compatible with database drivers like psycopg2.
class UserRole(str, enum.Enum):
    ADMIN = "admin"
    USER = "user"
    VIEW = "view"

    def __str__(self):
        return self.value


class CityTypeEnum(str, enum.Enum):
    SKLADISTE = "SKLADISTE"
    IJ = "IJ"

    def __str__(self):
        return self.value


class Cities(db.Model):
    __tablename__ = "cities"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    # 2. Use the Enum type here
    # native_enum=True tells Postgres to create a custom TYPE
    type: Mapped[Optional[CityTypeEnum]] = mapped_column(
        Enum(CityTypeEnum, native_enum=True, name="city_type_enum")
    )

    is_active: Mapped[Optional[bool]] = mapped_column(
        Boolean, server_default=text("true")
    )

    include_in_total: Mapped[Optional[bool]] = mapped_column(
        Boolean, server_default=text("true")
    )

    cpe_dismantle: Mapped[list["CpeDismantle"]] = relationship(
        "CpeDismantle", back_populates="city"
    )
    cpe_inventory: Mapped[list["CpeInventory"]] = relationship(
        "CpeInventory", back_populates="city"
    )
    ont_inventory: Mapped[list["OntInventory"]] = relationship(
        "OntInventory", back_populates="city"
    )
    users: Mapped[list["Users"]] = relationship("Users", back_populates="city")


class CpeTypes(db.Model):
    __tablename__ = "cpe_types"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    label: Mapped[Optional[str]] = mapped_column(String(200))

    # 2. Use the Enum type here
    # native_enum=True tells Postgres to create a custom TYPE
    type: Mapped[Optional[CpeTypeEnum]] = mapped_column(
        Enum(CpeTypeEnum, native_enum=True, name="cpe_type_enum")
    )

    is_visible_in_total: Mapped[Optional[bool]] = mapped_column(
        Boolean, server_default=text("true")
    )

    is_visible_in_dismantle: Mapped[Optional[bool]] = mapped_column(
        Boolean, server_default=text("true")
    )

    has_remote = mapped_column(Boolean, nullable=False, server_default="false")

    has_adapter = mapped_column(Boolean, nullable=False, server_default="true")

    display_order: Mapped[Optional[int]] = mapped_column(Integer)

    header_color: Mapped[Optional[str]] = mapped_column(String(50))

    cpe_dismantle: Mapped[list["CpeDismantle"]] = relationship(
        "CpeDismantle", back_populates="cpe_type"
    )
    cpe_inventory: Mapped[list["CpeInventory"]] = relationship(
        "CpeInventory", back_populates="cpe_type"
    )


class DismantleTypes(db.Model):
    __tablename__ = "dismantle_types"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    label: Mapped[Optional[str]] = mapped_column(String, nullable=False)
    group_name = mapped_column(String, nullable=False)

    cpe_dismantle: Mapped[list["CpeDismantle"]] = relationship(
        "CpeDismantle", back_populates="dismantle_type"
    )


class StbTypes(db.Model):
    __tablename__ = "stb_types"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="stb_types_pkey"),
        UniqueConstraint("name", name="stb_types_name_key"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    label: Mapped[Optional[str]] = mapped_column(String(200))

    stb_inventory: Mapped[list["StbInventory"]] = relationship(
        "StbInventory", back_populates="stb_type"
    )


class CpeDismantle(db.Model):
    __tablename__ = "cpe_dismantle"
    __table_args__ = (
        # UniqueConstraint for upsert (updat/insert) One row = one city + one CPE + one week
        UniqueConstraint(
            "city_id",
            "cpe_type_id",
            "dismantle_type_id",
            "week_end",
            name="uq_city_cpe_dismantle_week",
        ),
        # Data integrity only fridays of week is enforced at DB level
        CheckConstraint("EXTRACT(DOW FROM week_end) = 5", name="ck_week_end_friday"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    city_id: Mapped[int] = mapped_column(ForeignKey("cities.id"), nullable=False)
    cpe_type_id: Mapped[int] = mapped_column(ForeignKey("cpe_types.id"), nullable=False)
    dismantle_type_id: Mapped[int] = mapped_column(
        ForeignKey("dismantle_types.id"), nullable=False
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    week_end: Mapped[datetime.date] = mapped_column(Date, nullable=False)

    created_at: Mapped[datetime.datetime] = mapped_column(
       DateTime(timezone=True), server_default=text("now()")
    )

    updated_at = mapped_column(DateTime(timezone=True), nullable=True)

    city = relationship("Cities", back_populates="cpe_dismantle")
    cpe_type = relationship("CpeTypes", back_populates="cpe_dismantle")
    dismantle_type = relationship("DismantleTypes", back_populates="cpe_dismantle")


class CpeInventory(db.Model):
    __tablename__ = "cpe_inventory"
    __table_args__ = (
        # UniqueConstraint for upsert (updat/insert) One row = one city + one CPE + one week
        UniqueConstraint("city_id", "cpe_type_id", "week_end", name="uq_city_cpe_week"),
        # Data integrity only friday of week is enforced at DB level
        CheckConstraint("EXTRACT(DOW FROM week_end) = 5", name="ck_week_end_friday"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    city_id: Mapped[int] = mapped_column(ForeignKey("cities.id"), nullable=False)
    cpe_type_id: Mapped[int] = mapped_column(ForeignKey("cpe_types.id"), nullable=False)
    week_end: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)

    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
        # You want updated_at to change automatically whenever quantity changes
        onupdate=text("now()"),
    )

    city = relationship("Cities", back_populates="cpe_inventory")
    cpe_type = relationship("CpeTypes", back_populates="cpe_inventory")


class OntInventory(db.Model):
    __tablename__ = "ont_inventory"
    __table_args__ = (
        ForeignKeyConstraint(["city_id"], ["cities.id"], name="fk_city"),
        PrimaryKeyConstraint("id", name="ont_inventory_pkey"),
        UniqueConstraint("city_id", "month_end", name="uq_ont_moonth"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    month_end: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    city_id: Mapped[Optional[int]] = mapped_column(Integer)
    quantity: Mapped[Optional[int]] = mapped_column(Integer)

    city: Mapped[Optional["Cities"]] = relationship(
        "Cities", back_populates="ont_inventory"
    )


class StbInventory(db.Model):
    __tablename__ = "stb_inventory"
    __table_args__ = (
        ForeignKeyConstraint(["stb_type_id"], ["stb_types.id"], name="fk_stb_type"),
        PrimaryKeyConstraint("id", name="stb_inventory_pkey"),
        UniqueConstraint("stb_type_id", "week_end", name="uq_stb_week"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    week_end: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    stb_type_id: Mapped[Optional[int]] = mapped_column(Integer)
    quantity: Mapped[Optional[int]] = mapped_column(Integer)

    stb_type: Mapped[Optional["StbTypes"]] = relationship(
        "StbTypes", back_populates="stb_inventory"
    )


class IptvUsers(db.Model):
    __tablename__ = "iptv_users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    total_users: Mapped[int] = mapped_column(Integer, nullable=False)
    # Adding 'unique=True' prevents duplicate entries for the same week
    # A column should be UNIQUE only if it fully identifies the row by itself.
    week_end: Mapped[datetime.date] = mapped_column(Date, nullable=False, unique=True)
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),  # Recommended for Postgres
        server_default=text("now()"),
        onupdate=text("now()"),
    )


class Users(db.Model, UserMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)

    # 2. Apply the Enum here
    role: Mapped[UserRole] = mapped_column(
        Enum(
            UserRole,
            native_enum=True,
            name="user_role_enum",
            # This tells SQLAlchemy to use the values ('admin') instead of names ('ADMIN')
            values_callable=lambda x: [item.value for item in x],
        ),
        nullable=False,
        # Default must match the Enum value
        server_default=text("'user'"),
    )

    city_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("cities.id", name="fk_city")
    )
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(timezone=True),
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=text("CURRENT_TIMESTAMP"),
    )

    city: Mapped[Optional["Cities"]] = relationship("Cities", back_populates="users")


class ReportSetting(db.Model):
    __tablename__ = "report_settings"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    # 0=Mon ... 6=Sun
    send_day: Mapped[int] = mapped_column(Integer, nullable=False)

    send_time: Mapped[datetime.time] = mapped_column(Time, nullable=False)

    last_sent_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    updated_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )

class ReportRecipients(db.Model):
    __tablename__ = "report_recipients"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    active: Mapped[bool] = mapped_column(Boolean, default=True)

    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


# DDL (Data Definition Language) listener in SQLAlchemy.
# SQLAlchemy needs to "create" the custom type in the database
# before it can "use" it in a table definition.
# IN THIS CASE create:
# USER ENUM before USERS TABLE and
# CpeTypeEnum before CPETYPES TABLE
# 2. Function to generate "If Not Exists" DDL for any Enum
def setup_enum_ddl(enum_name, enum_values, table_object):
    values_str = ", ".join(f"'{v}'" for v in enum_values)
    ddl = DDL(f"""
        DO $$ 
        BEGIN 
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = '{enum_name}') THEN 
                CREATE TYPE {enum_name} AS ENUM ({values_str}); 
            END IF; 
        END $$;
    """)
    event.listen(table_object, "before_create", ddl.execute_if(dialect="postgresql"))


# Register the event: Create the type BEFORE the tables are created
# We check 'if not exists' via a helper or just let the script run
# IN THIS CASE create USER ENUM before USERS TABLE
# 3. Register them for your specific tables
setup_enum_ddl("user_role_enum", [r.value for r in UserRole], Users.__table__)
setup_enum_ddl("cpe_type_enum", [c.value for c in CpeTypeEnum], CpeTypes.__table__)
setup_enum_ddl("city_type_enum", [c.value for c in CityTypeEnum], Cities.__table__)
