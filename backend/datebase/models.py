#!/usr/bin/python3
# -*- coding:utf-8 -*-
"""SQLAlchemy 2.0 异步 ORM 模型定义。"""

from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import ForeignKey, JSON, Text, String, Integer, DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class ModeConfig(Base):
    """讨论模式配置（如六顶思考帽、辩论赛）。"""
    __tablename__ = "mode_configs"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(100))
    description: Mapped[Optional[str]] = mapped_column(Text, default=None)
    mode_json: Mapped[dict] = mapped_column(JSON, default=dict)
    default_rounds: Mapped[int] = mapped_column(Integer, default=3)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, onupdate=utc_now
    )

    participants: Mapped[List["Participant"]] = relationship(
        back_populates="mode",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class Participant(Base):
    """某模式下的角色定义。"""
    __tablename__ = "participants"

    id: Mapped[int] = mapped_column(primary_key=True)
    mode_name: Mapped[str] = mapped_column(
        ForeignKey("mode_configs.name"), index=True
    )
    role_key: Mapped[str] = mapped_column(String(50))
    name: Mapped[str] = mapped_column(String(100))
    model: Mapped[str] = mapped_column(String(100))
    color: Mapped[Optional[str]] = mapped_column(String(20), default=None)
    system_prompt: Mapped[str] = mapped_column(Text, default="")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    tools_enabled: Mapped[Optional[str]] = mapped_column(Text, default=None)  # JSON 数组，如 '["search"]'

    mode: Mapped["ModeConfig"] = relationship(back_populates="participants")

    __table_args__ = (
        # 同一模式下 role_key 唯一
        {"sqlite_autoincrement": True},
    )


class SessionRecord(Base):
    """一场讨论的 Session 记录。"""
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    mode: Mapped[str] = mapped_column(String(50), index=True)
    topic: Mapped[str] = mapped_column(Text)
    rounds: Mapped[int] = mapped_column(Integer, default=3)
    status: Mapped[str] = mapped_column(
        String(20), default="pending"
    )  # pending / running / completed / error
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=None)

    messages: Mapped[List["Message"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="Message.ts",
        lazy="selectin",
    )
    attachments: Mapped[List["Attachment"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class Attachment(Base):
    """用户上传的文件记录。"""
    __tablename__ = "attachments"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), index=True
    )
    filename: Mapped[str] = mapped_column(String(255))
    file_type: Mapped[str] = mapped_column(String(20))  # pdf, docx, txt, md, xlsx, pptx
    file_size: Mapped[int] = mapped_column(Integer)
    storage_path: Mapped[str] = mapped_column(String(500))
    summary: Mapped[Optional[str]] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    session: Mapped["SessionRecord"] = relationship(back_populates="attachments")


class Message(Base):
    """单条发言记录。"""
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("sessions.id"), index=True
    )
    role_key: Mapped[str] = mapped_column(String(50))
    role: Mapped[str] = mapped_column(String(20))  # assistant / user
    name: Mapped[str] = mapped_column(String(100))
    content: Mapped[str] = mapped_column(Text)
    model: Mapped[Optional[str]] = mapped_column(String(100), default=None)
    ts: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    session: Mapped["SessionRecord"] = relationship(back_populates="messages")


class GlobalHost(Base):
    """全局主持人配置（所有模式共享）。"""
    __tablename__ = "global_hosts"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), default="主持人")
    model: Mapped[str] = mapped_column(String(100), default="deepseek/deepseek-reasoner")
    system_prompt: Mapped[str] = mapped_column(Text, default="")
    # 颜色固定为蓝色 ANSI 码，不允许修改
    color: Mapped[str] = mapped_column(String(20), default="[34m")


class Provider(Base):
    """LLM 供应商配置。"""
    __tablename__ = "providers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    base_url: Mapped[Optional[str]] = mapped_column(String(255), default=None)
    api_key: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    models: Mapped[List["ProviderModel"]] = relationship(
        back_populates="provider",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class ProviderModel(Base):
    """供应商下的可用模型。"""
    __tablename__ = "provider_models"

    id: Mapped[int] = mapped_column(primary_key=True)
    provider_id: Mapped[int] = mapped_column(ForeignKey("providers.id"), index=True)
    model_name: Mapped[str] = mapped_column(String(100))

    provider: Mapped["Provider"] = relationship(back_populates="models")
