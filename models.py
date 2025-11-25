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


class Cities(db.Model):
    __tablename__ = "cities"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="cities_pkey"),
        UniqueConstraint("name", name="cities_name_key"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)

    cpe_records: Mapped[list["CpeRecords"]] = relationship(
        "CpeRecords", back_populates="city"
    )
    users: Mapped[list["Users"]] = relationship("Users", back_populates="city")


class CpeRecords(db.Model):
    __tablename__ = "cpe_records"
    __table_args__ = (
        ForeignKeyConstraint(
            ["city_id"], ["cities.id"], name="cpe_records_city_id_fkey"
        ),
        PrimaryKeyConstraint("id", name="cpe_records_pkey"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    record_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    city_id: Mapped[Optional[int]] = mapped_column(Integer)
    iad267: Mapped[Optional[int]] = mapped_column(Integer)
    stb_arr_4205: Mapped[Optional[int]] = mapped_column(Integer)
    stb_arr_5305: Mapped[Optional[int]] = mapped_column(Integer)
    stb_ekt_4805: Mapped[Optional[int]] = mapped_column(Integer)
    stb_ekt_7005: Mapped[Optional[int]] = mapped_column(Integer)
    stb_sky_44: Mapped[Optional[int]] = mapped_column(Integer)
    ont_hw: Mapped[Optional[int]] = mapped_column(Integer)
    ont_no: Mapped[Optional[int]] = mapped_column(Integer)
    dth: Mapped[Optional[int]] = mapped_column(Integer)
    antena: Mapped[Optional[int]] = mapped_column(Integer)
    lnb: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime, server_default=text("now()")
    )

    city: Mapped[Optional["Cities"]] = relationship(
        "Cities", back_populates="cpe_records"
    )


# UserMixin automatically provides:
# is_authenticated
# is_active
# is_anonymous
# get_id()
# Exactly what Flask-Login needs.
class Users(db.Model, UserMixin):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "role::text = ANY (ARRAY['admin'::character varying, 'user'::character varying]::text[])",
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
