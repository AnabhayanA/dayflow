from typing import List, Optional

from pydantic import BaseModel, Field


class Task(BaseModel):
    id: int
    title: str
    category: str = "School"
    date: Optional[str] = None
    duration: int = Field(gt=0)
    priority: str = "medium"
    completed: bool = False
    starred: bool = False


class FixedBlock(BaseModel):
    id: int
    title: str
    type: str = "Personal"
    day: int = Field(ge=0, le=6)
    start: str
    end: str


class AvailabilityWindow(BaseModel):
    day: int = Field(ge=0, le=6)
    start: str = "08:00"
    end: str = "21:00"


class Profile(BaseModel):
    name: str = "You"
    availability: List[AvailabilityWindow] = Field(default_factory=list)
    focus_minutes: int = 90
    break_minutes: int = 15


class PlanRequest(BaseModel):
    tasks: List[Task]
    fixed_blocks: List[FixedBlock] = Field(default_factory=list)
    availability: List[AvailabilityWindow] = Field(default_factory=list)
    week_start: Optional[str] = None


class ScheduleBlock(BaseModel):
    task_id: int
    title: str
    category: str
    date: str
    day: int
    start: str
    end: str
    duration: int
    priority: str


class PlanResponse(BaseModel):
    message: str
    total_minutes: int
    scheduled_minutes: int
    unscheduled_minutes: int
    schedule: List[ScheduleBlock]


class MeetingParticipant(BaseModel):
    name: str
    availability: List[AvailabilityWindow] = Field(default_factory=list)


class MeetingRequest(BaseModel):
    title: str
    duration: int = Field(gt=0)
    urgency: str = "normal"
    participants: List[MeetingParticipant] = Field(default_factory=list)
    fixed_blocks: List[FixedBlock] = Field(default_factory=list)
    availability: List[AvailabilityWindow] = Field(default_factory=list)
    week_start: Optional[str] = None
    preferred_after: Optional[str] = None
    preferred_before: Optional[str] = None


class MeetingOption(BaseModel):
    id: int
    date: str
    day: int
    start: str
    end: str
    score: int
    reason: str


class MeetingResponse(BaseModel):
    options: List[MeetingOption]


class ChatRequest(BaseModel):
    message: str
    tasks: List[Task] = Field(default_factory=list)
    fixed_blocks: List[FixedBlock] = Field(default_factory=list)


class ChatResponse(BaseModel):
    message: str
    action: Optional[str] = None
