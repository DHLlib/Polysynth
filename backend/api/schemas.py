#!/usr/bin/python3
# -*- coding:utf-8 -*-
"""Pydantic 请求/响应模型。"""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel


class ParticipantOut(BaseModel):
    id: int
    role_key: str
    name: str
    model: str
    color: Optional[str]
    system_prompt: str
    sort_order: int
    tools_enabled: Optional[str]

    class Config:
        from_attributes = True


class ModeConfigOut(BaseModel):
    id: int
    name: str
    display_name: str
    description: Optional[str]
    default_rounds: int
    mode_json: dict
    participants: list[ParticipantOut]

    class Config:
        from_attributes = True


class SessionCreate(BaseModel):
    mode: Literal["six_hat", "debate"]
    topic: str
    rounds: Optional[int] = None


class ModeConfigUpdate(BaseModel):
    default_rounds: Optional[int] = None


class SessionOut(BaseModel):
    id: str
    mode: str
    topic: str
    rounds: int
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class MessageOut(BaseModel):
    id: int
    role_key: str
    role: str
    name: str
    content: str
    model: Optional[str]
    ts: datetime

    class Config:
        from_attributes = True


class SessionDetailOut(SessionOut):
    messages: list[MessageOut]


class ProviderModelOut(BaseModel):
    id: int
    model_name: str

    class Config:
        from_attributes = True


class ProviderOut(BaseModel):
    id: int
    name: str
    base_url: Optional[str]
    api_key: str
    models: list[ProviderModelOut]

    class Config:
        from_attributes = True


class ProviderCreate(BaseModel):
    name: str
    base_url: Optional[str] = None
    api_key: str


class ProviderUpdate(BaseModel):
    name: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None


class ProviderModelCreate(BaseModel):
    model_name: str


class GlobalHostOut(BaseModel):
    id: int
    name: str
    model: str
    system_prompt: str
    color: str

    class Config:
        from_attributes = True


class GlobalHostUpdate(BaseModel):
    name: Optional[str] = None
    model: Optional[str] = None
    system_prompt: Optional[str] = None
