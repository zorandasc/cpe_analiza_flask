from typing import Optional
import datetime

from sqlalchemy import (
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


db = SQLAlchemy()

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

    cpe_dismantle_records: Mapped[list["CpeDismantleRecords"]] = relationship(
        "CpeDismantleRecords", back_populates="city"
    )
    cpe_records: Mapped[list["CpeRecords"]] = relationship(
        "CpeRecords", back_populates="city"
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
    type: Mapped[Optional[str]] = mapped_column(String(100))

    cpe_dismantle_records: Mapped[list["CpeDismantleRecords"]] = relationship(
        "CpeDismantleRecords", back_populates="cpe_type"
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

    cpe_dismantle_records: Mapped[list["CpeDismantleRecords"]] = relationship(
        "CpeDismantleRecords", back_populates="dismantle_type"
    )


class CpeDismantleRecords(db.Model):
    __tablename__ = "cpe_dismantle_records"
    __table_args__ = (
        ForeignKeyConstraint(
            ["city_id"], ["cities.id"], name="cpe_dismantle_records_city_id_fkey"
        ),
        ForeignKeyConstraint(
            ["cpe_type_id"],
            ["cpe_types.id"],
            name="cpe_dismantle_records_cpe_type_id_fkey",
        ),
        ForeignKeyConstraint(
            ["dismantle_type_id"],
            ["dismantle_types.id"],
            name="cpe_dismantle_records_dismantle_type_id_fkey",
        ),
        PrimaryKeyConstraint("id", name="cpe_dismantle_records_pkey"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    city_id: Mapped[Optional[int]] = mapped_column(Integer)
    cpe_type_id: Mapped[Optional[int]] = mapped_column(Integer)
    quantity: Mapped[Optional[int]] = mapped_column(Integer)
    dismantle_type_id: Mapped[Optional[int]] = mapped_column(Integer)
    day_date: Mapped[Optional[datetime.date]] = mapped_column(
        Date, server_default=text("now()")
    )

    city: Mapped[Optional["Cities"]] = relationship(
        "Cities", back_populates="cpe_dismantle_records"
    )
    cpe_type: Mapped[Optional["CpeTypes"]] = relationship(
        "CpeTypes", back_populates="cpe_dismantle_records"
    )
    dismantle_type: Mapped[Optional["DismantleTypes"]] = relationship(
        "DismantleTypes", back_populates="cpe_dismantle_records"
    )


class CpeRecords(db.Model):
    __tablename__ = "cpe_records"
    __table_args__ = (
        ForeignKeyConstraint(
            ["city_id"], ["cities.id"], name="cpe_records_city_id_fkey"
        ),
        PrimaryKeyConstraint("id", name="cpe_records_pkey"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    city_id: Mapped[Optional[int]] = mapped_column(Integer)
    iads: Mapped[Optional[int]] = mapped_column(Integer)
    stb_arr_4205: Mapped[Optional[int]] = mapped_column(Integer)
    stb_arr_5305: Mapped[Optional[int]] = mapped_column(Integer)
    stb_ekt_4805: Mapped[Optional[int]] = mapped_column(Integer)
    stb_ekt_7005: Mapped[Optional[int]] = mapped_column(Integer)
    stb_sky_44h: Mapped[Optional[int]] = mapped_column(Integer)
    ont_huaw: Mapped[Optional[int]] = mapped_column(Integer)
    ont_nok: Mapped[Optional[int]] = mapped_column(Integer)
    stb_dth: Mapped[Optional[int]] = mapped_column(Integer)
    antena_dth: Mapped[Optional[int]] = mapped_column(Integer)
    lnb_duo: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime, server_default=text("now()")
    )
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime, server_default=text("now()")
    )

    city: Mapped[Optional["Cities"]] = relationship(
        "Cities", back_populates="cpe_records"
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
