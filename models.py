from typing import Optional
from pydantic import BaseModel


# ── Areas ──────────────────────────────────────────────

class AreaCreate(BaseModel):
    name: str
    interval_min: int = 30


class AreaUpdate(BaseModel):
    name: Optional[str] = None
    interval_min: Optional[int] = None


class AreaOut(BaseModel):
    id: int
    name: str
    interval_min: int


# ── Staff ──────────────────────────────────────────────

class StaffCreate(BaseModel):
    name: str


class StaffOut(BaseModel):
    id: int
    name: str


# ── Shifts ─────────────────────────────────────────────

class ShiftCreate(BaseModel):
    staff_id: int
    day_of_week: int
    shift_start: str
    shift_end: str


class ShiftOut(BaseModel):
    id: int
    staff_id: int
    staff_name: str
    day_of_week: int
    shift_start: str
    shift_end: str


# ── Logs ───────────────────────────────────────────────

class LogCreate(BaseModel):
    area_id: int
    staff_id: Optional[int] = None


class LogOut(BaseModel):
    id: int
    area_id: int
    area_name: str
    staff_id: Optional[int]
    staff_name: Optional[str]
    action: str
    alarm_time: str
    confirmed_at: Optional[str]
