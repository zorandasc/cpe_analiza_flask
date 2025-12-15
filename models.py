from typing import Optional
import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKeyConstraint,
    Integer,
    PrimaryKeyConstraint,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

CPE_TYPE_CHOICES = [
    "IAD",
    "ONT",
    "STB",
    "ANTENA",
    "ROUTER",
    "SWITCH",
    "WIFI EXTENDER",
    "WIFI ACCESS POINT",
    "PHONES",
    "SERVER",
    "PC",
    "IOT",
]

db = SQLAlchemy()


class Cities(db.Model):
    __tablename__ = "cities"
    __table_args__ = (
        CheckConstraint(
            "type::text = ANY (ARRAY['IJ'::character varying, 'Skladiste'::character varying]::text[])",
            name="cities_type_check",
        ),
        PrimaryKeyConstraint("id", name="cities_pkey"),
        UniqueConstraint("name", name="cities_name_key"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    type: Mapped[Optional[str]] = mapped_column(String(100))

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
    __table_args__ = (
        CheckConstraint(
            sqltext=f"type::text = ANY (ARRAY[{', '.join(f"'{c}'::character varying" for c in CPE_TYPE_CHOICES)}]::text[])",
            name="cpe_types_type_check",
        ),
        PrimaryKeyConstraint("id", name="cpe_types_pkey"),
        UniqueConstraint("name", name="cpe_types_name_key"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    label: Mapped[Optional[str]] = mapped_column(String(200))
    type: Mapped[Optional[str]] = mapped_column(String(100))
    is_active: Mapped[Optional[bool]] = mapped_column(
        Boolean, server_default=text("true")
    )

    cpe_dismantle: Mapped[list["CpeDismantle"]] = relationship(
        "CpeDismantle", back_populates="cpe_type"
    )
    cpe_inventory: Mapped[list["CpeInventory"]] = relationship(
        "CpeInventory", back_populates="cpe_type"
    )


class DismantleTypes(db.Model):
    __tablename__ = "dismantle_types"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="dismantle_types_pkey"),
        UniqueConstraint("label", name="dismantle_types_label_key"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    label: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(100))

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
        ForeignKeyConstraint(
            ["city_id"], ["cities.id"], name="cpe_dismantle_city_id_fkey"
        ),
        ForeignKeyConstraint(
            ["cpe_type_id"], ["cpe_types.id"], name="cpe_dismantle_cpe_type_id_fkey"
        ),
        ForeignKeyConstraint(
            ["dismantle_type_id"],
            ["dismantle_types.id"],
            name="cpe_dismantle_dismantle_type_id_fkey",
        ),
        PrimaryKeyConstraint("id", name="cpe_dismantle_pkey"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    city_id: Mapped[Optional[int]] = mapped_column(Integer)
    cpe_type_id: Mapped[Optional[int]] = mapped_column(Integer)
    quantity: Mapped[Optional[int]] = mapped_column(Integer)
    dismantle_type_id: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime, server_default=text("now()")
    )
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime, server_default=text("now()")
    )

    city: Mapped[Optional["Cities"]] = relationship(
        "Cities", back_populates="cpe_dismantle"
    )
    cpe_type: Mapped[Optional["CpeTypes"]] = relationship(
        "CpeTypes", back_populates="cpe_dismantle"
    )
    dismantle_type: Mapped[Optional["DismantleTypes"]] = relationship(
        "DismantleTypes", back_populates="cpe_dismantle"
    )


class CpeInventory(db.Model):
    __tablename__ = "cpe_inventory"
    __table_args__ = (
        ForeignKeyConstraint(
            ["city_id"], ["cities.id"], name="cpe_inventory_city_id_fkey"
        ),
        ForeignKeyConstraint(
            ["cpe_type_id"], ["cpe_types.id"], name="cpe_inventory_cpe_type_id_fkey"
        ),
        PrimaryKeyConstraint("id", name="cpe_inventory_pkey"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    city_id: Mapped[Optional[int]] = mapped_column(Integer)
    cpe_type_id: Mapped[Optional[int]] = mapped_column(Integer)
    quantity: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime, server_default=text("now()")
    )
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime, server_default=text("now()")
    )

    city: Mapped[Optional["Cities"]] = relationship(
        "Cities", back_populates="cpe_inventory"
    )
    cpe_type: Mapped[Optional["CpeTypes"]] = relationship(
        "CpeTypes", back_populates="cpe_inventory"
    )


class OntInventory(db.Model):
    __tablename__ = "ont_inventory"
    __table_args__ = (
        ForeignKeyConstraint(["city_id"], ["cities.id"], name="fk_city"),
        PrimaryKeyConstraint("id", name="ont_inventory_pkey"),
        UniqueConstraint("city_id", "month_end", name="uq_ont_moonth"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    month_end: Mapped[datetime.date] = mapped_column(Date, nullable=False)
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
    stb_type_id: Mapped[Optional[int]] = mapped_column(Integer)
    quantity: Mapped[Optional[int]] = mapped_column(Integer)

    stb_type: Mapped[Optional["StbTypes"]] = relationship(
        "StbTypes", back_populates="stb_inventory"
    )


class Users(db.Model, UserMixin):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "role::text = ANY (ARRAY['admin'::character varying, 'user'::character varying, 'view'::character varying]::text[])",
            name="chk_user_role",
        ),
        ForeignKeyConstraint(["city_id"], ["cities.id"], name="fk_city"),
        PrimaryKeyConstraint("id", name="users_pkey"),
        UniqueConstraint("username", name="users_username_key"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(50), nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'user'::character varying")
    )
    city_id: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(True), server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(True), server_default=text("CURRENT_TIMESTAMP")
    )

    city: Mapped[Optional["Cities"]] = relationship("Cities", back_populates="users")
