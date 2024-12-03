from typing import List
from typing import Optional
from sqlalchemy import ForeignKey
from sqlalchemy import (
    String,
    Integer,
    Boolean,
    UniqueConstraint,
    Float,
    Column,
    Table,
    DateTime,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
import datetime
from automatic_university_scheduler.datetimeutils import DateTime as DT
from automatic_university_scheduler.datetimeutils import TimeDelta, datetime_to_slot
import math
import numpy as np
import networkx as nx
import pandas as pd


class Base(DeclarativeBase):
    pass


# ASSOSIATION TABLES

activity_room_pool_association_table = Table(
    "activity_room_pool_association_table",
    Base.metadata,
    Column("activity_id", ForeignKey("activity.id"), primary_key=True),
    Column("room_id", ForeignKey("room.id"), primary_key=True),
)

activity_room_allocation_association_table = Table(
    "activity_room_allocation_association_table",
    Base.metadata,
    Column("activity_id", ForeignKey("activity.id"), primary_key=True),
    Column("room_id", ForeignKey("room.id"), primary_key=True),
)

static_activity_room_allocation_association_table = Table(
    "static_activity_room_allocation_association_table",
    Base.metadata,
    Column("static_activity_id", ForeignKey("static_activity.id"), primary_key=True),
    Column("room_id", ForeignKey("room.id"), primary_key=True),
)

activity_teacher_pool_association_table = Table(
    "activity_teacher_pool_association_table",
    Base.metadata,
    Column("activity_id", ForeignKey("activity.id"), primary_key=True),
    Column("teacher_id", ForeignKey("teacher.id"), primary_key=True),
)

activity_teacher_allocation_association_table = Table(
    "activity_teacher_allocation_association_table",
    Base.metadata,
    Column("activity_id", ForeignKey("activity.id"), primary_key=True),
    Column("teacher_id", ForeignKey("teacher.id"), primary_key=True),
)

static_activity_teacher_allocation_association_table = Table(
    "static_activity_teacher_allocation_association_table",
    Base.metadata,
    Column("static_activity_id", ForeignKey("static_activity.id"), primary_key=True),
    Column("teacher_id", ForeignKey("teacher.id"), primary_key=True),
)

student_atomic_groups_association_table = Table(
    "student_atomic_groups_association_table",
    Base.metadata,
    Column("atom_id", ForeignKey("atomic_student.id"), primary_key=True),
    Column("group_id", ForeignKey("students_group.id"), primary_key=True),
)

activity_groups_association_table = Table(
    "activity_groups_association_table",
    Base.metadata,
    Column("activity_id", ForeignKey("activity.id"), primary_key=True),
    Column("activity_group_id", ForeignKey("activity_group.id"), primary_key=True),
)

activity_kind_daily_slots_association_table = Table(
    "activity_kind_daily_slots_association_table",
    Base.metadata,
    Column("activity_kind_id", ForeignKey("activity_kind.id"), primary_key=True),
    Column("daily_slot_id", ForeignKey("daily_slot.id"), primary_key=True),
)


class Project(Base):
    __tablename__ = "project"
    _unique_columns = ["label"]

    id: Mapped[int] = mapped_column(primary_key=True)
    label: Mapped[str] = mapped_column(String(30), unique=True)
    description: Mapped[str] = mapped_column(String(255), nullable=True)
    origin_datetime: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    horizon: Mapped[int] = mapped_column(Integer, nullable=False)
    time_slot_duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    succession_constraint_relaxation_factor: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    activities: Mapped[List["Activity"]] = relationship(
        "Activity", back_populates="project"
    )
    static_activities: Mapped[List["StaticActivity"]] = relationship(
        "StaticActivity", back_populates="project"
    )
    students_groups: Mapped[List["StudentsGroup"]] = relationship(
        "StudentsGroup", back_populates="project"
    )
    atomic_students: Mapped[List["AtomicStudent"]] = relationship(
        "AtomicStudent", back_populates="project"
    )
    activity_groups: Mapped[List["ActivityGroup"]] = relationship(
        "ActivityGroup", back_populates="project"
    )
    starts_after_constraints: Mapped[List["StartsAfterConstraint"]] = relationship(
        "StartsAfterConstraint", back_populates="project"
    )
    daily_slots: Mapped[List["DailySlot"]] = relationship(
        "DailySlot", back_populates="project"
    )
    activity_kinds: Mapped[List["ActivityKind"]] = relationship(
        "ActivityKind", back_populates="project"
    )
    week_days: Mapped[List["WeekDay"]] = relationship(
        "WeekDay", back_populates="project"
    )
    week_slots_availability: Mapped[List["WeekSlotsAvailabiblity"]] = relationship(
        "WeekSlotsAvailabiblity", back_populates="project"
    )
    courses: Mapped[List["Course"]] = relationship("Course", back_populates="project")
    teachers: Mapped[List["Teacher"]] = relationship(
        "Teacher", back_populates="project"
    )
    planners: Mapped[List["Planner"]] = relationship(
        "Planner", back_populates="project"
    )
    managers: Mapped[List["Manager"]] = relationship(
        "Manager", back_populates="project"
    )
    rooms: Mapped[List["Room"]] = relationship("Room", back_populates="project")

    __table_args__ = (UniqueConstraint(*_unique_columns, name="_unique_project"),)

    def __repr__(self) -> str:
        name = self.__class__.__name__
        return f"<{name}: id={self.id}, label={self.label}>"

    @property
    def origin(self):
        return DT.from_datetime(self.origin_datetime)

    # @property
    # def horizon(self):
    #     return DT.from_datetime(self.horizon_datetime)

    @property
    def time_slot_duration(self):
        return TimeDelta(seconds=self.time_slot_duration_seconds)

    @property
    def time_slots_per_day(self):
        return math.floor(24 * 3600 / self.time_slot_duration_seconds)

    @property
    def time_slots_per_week(self):
        return self.time_slots_per_day * 7

    @property
    def week_structure(self):
        spw = self.time_slots_per_week
        spd = self.time_slots_per_day
        ws = np.zeros((spd, 7), dtype=int)
        for slot in self.week_slots_availability:
            if slot.available:
                ws[slot.daily_slot_id - 1, slot.week_day_id - 1] = 1
        return ws

    @property
    def setup(self):
        """
        Load the setup file.
        """
        horizon = self.horizon
        origin_datetime = self.origin
        time_slot_duration = self.time_slot_duration
        horizon_datetime = self.origin + horizon * time_slot_duration
        origin_monday = DT.fromisocalendar(
            origin_datetime.isocalendar().year, origin_datetime.isocalendar().week, 1
        )
        horizon_monday = DT.fromisocalendar(
            horizon_datetime.isocalendar().year, horizon_datetime.isocalendar().week, 1
        )
        out = {}
        out["WEEK_STRUCTURE"] = self.week_structure
        ONE_WEEK = TimeDelta.from_str("1w")
        ONE_DAY = TimeDelta.from_str("1d")
        out["DAYS_PER_WEEK"] = 7
        out["TIME_SLOTS_PER_DAY"] = ONE_DAY // time_slot_duration
        out["ORIGIN_DATETIME"] = origin_datetime
        out["HORIZON_DATETIME"] = horizon_datetime
        # out["HORIZON_MONDAY"] = horizon_monday
        out["ORIGIN_MONDAY"] = origin_monday
        out["MAX_WEEKS"] = (horizon_monday - origin_monday) // ONE_WEEK + 1
        out["TIME_SLOT_DURATION"] = time_slot_duration
        out["TIME_SLOTS_PER_WEEK"] = out["DAYS_PER_WEEK"] * out["TIME_SLOTS_PER_DAY"]
        out["HORIZON"] = horizon
        out["SUCCESSION_CONSTRAINT_RELAXATION_FACTOR"] = self.succession_constraint_relaxation_factor
        return out

    def duration_to_slots(self, duration):
        if type(duration) == int:
            return duration
        elif type(duration) == str:
            return TimeDelta.from_str(duration).to_slots(
                slot_duration=self.time_slot_duration
            )
        elif duration == None:
            return None
        else:
            raise ValueError("Duration must be either an integer or a string")

    def slots_to_duration(self, slots):
        if slots == None:
            return None
        else:
            return TimeDelta(seconds=slots * self.time_slot_duration_seconds)

    def slots_to_datetime(self, slots):
        if slots == None:
            return None
        else:
            return DT.from_datetime(
                slots * self.time_slot_duration + self.origin_datetime
            )

    def datetime_to_slot(self, dt, round="floor"):
        if type(dt) == str:
            dt = DT.from_str(dt)
        slot = (dt - self.origin_datetime).to_slots(
            slot_duration=self.time_slot_duration
        )
        if round == "ceil":
            return math.ceil(slot)
        elif round == "floor":
            return math.floor(slot)


class AtomicStudent(Base):
    __tablename__ = "atomic_student"
    _unique_columns = ["label"]

    id: Mapped[int] = mapped_column(primary_key=True)
    label: Mapped[str] = mapped_column(String(30), unique=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("project.id"))
    project: Mapped["Project"] = relationship(back_populates="atomic_students")

    __table_args__ = (
        UniqueConstraint(*_unique_columns, name="_unique_atomic_student"),
    )

    groups: Mapped[List["StudentsGroup"]] = relationship(
        secondary=student_atomic_groups_association_table,
        back_populates="students",
    )

    def __repr__(self) -> str:
        name = self.__class__.__name__
        return f"<{name}: id={self.id}, label={self.label}>"

    @property
    def activities(self):
        return [activity for group in self.groups for activity in group.activities]


class StudentsGroup(Base):
    __tablename__ = "students_group"
    _unique_columns = ["label"]

    id: Mapped[int] = mapped_column(primary_key=True)
    label: Mapped[str] = mapped_column(String(30), unique=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("project.id"))
    project: Mapped["Project"] = relationship(back_populates="students_groups")

    __table_args__ = (
        UniqueConstraint(*_unique_columns, name="_unique_student_groups"),
    )

    students: Mapped[List["AtomicStudent"]] = relationship(
        secondary=student_atomic_groups_association_table,
        back_populates="groups",
    )

    activities: Mapped[List["Activity"]] = relationship(
        "Activity", back_populates="students"
    )

    static_activities: Mapped[List["StaticActivity"]] = relationship(
        "StaticActivity", back_populates="students"
    )

    def __repr__(self) -> str:
        name = self.__class__.__name__
        return f"<{name}: id={self.id}, label={self.label}>"


class StaticActivity(Base):
    __tablename__ = "static_activity"
    # _unique_columns = ["id"]

    id: Mapped[int] = mapped_column(primary_key=True)
    label: Mapped[str] = mapped_column(String(30))
    kind: Mapped[str] = mapped_column(String(30), nullable=True)
    start: Mapped[int] = mapped_column(Integer, nullable=True)
    duration: Mapped[int] = mapped_column(Integer, nullable=False)
    course: Mapped[str] = mapped_column(String(30), nullable=True)
    students_id: Mapped[int] = mapped_column(
        ForeignKey("students_group.id"), nullable=True
    )
    students: Mapped["StudentsGroup"] = relationship(back_populates="static_activities")
    project_id: Mapped[int] = mapped_column(ForeignKey("project.id"))
    project: Mapped["Project"] = relationship(back_populates="static_activities")

    # ROOMS
    allocated_rooms: Mapped[List["Room"]] = relationship(
        secondary=static_activity_room_allocation_association_table,
        back_populates="static_activities_allocations",
    )
    # TEACHER
    allocated_teachers: Mapped[List["Teacher"]] = relationship(
        secondary=static_activity_teacher_allocation_association_table,
        back_populates="static_activities_allocations",
    )

    # __table_args__ = (UniqueConstraint(*_unique_columns, name="_unique_static_activity"),)

    def __repr__(self) -> str:
        name = self.__class__.__name__
        return f"<{name}: id={self.id}, name={self.label}, kind={self.kind}, start={self.start}, duration={self.duration}>"

    @property
    def end(self):
        return self.start + self.duration

    @property
    def start_datetime(self):
        return self.project.slots_to_datetime(self.start)

    @property
    def end_datetime(self):
        return self.project.slots_to_datetime(self.end)

    @property
    def duration_timedelta(self):
        return self.project.slots_to_duration(self.duration)

    @property
    def planification_to_series(self):
        start = self.start_datetime
        end = self.end_datetime
        start_isocalendar = start.isocalendar()
        week = start_isocalendar.week
        weekday = start_isocalendar.weekday
        year = start_isocalendar.year
        start_clock = f"{start.hour:02d}:{start.minute:02d}"
        end_clock = f"{end.hour:02d}:{end.minute:02d}"
        duration = self.duration_timedelta.to_str()
        if self.students is not None:
            students = self.students.label
        else:
            students = None
        out = {
            "id": self.id,
            "label": self.label,
            "kind": self.kind,
            "start_slot": self.start,
            "year": year,
            "week": week,
            "weekday": weekday,
            "start": start_clock,
            "end": end_clock,
            "duration": duration,
            "students": students,
            "allocated_teachers": ", ".join(
                [t.full_name for t in self.allocated_teachers]
            ),
            "allocated_rooms": ", ".join([r.label for r in self.allocated_rooms]),
        }
        return pd.Series(out)


class Activity(Base):
    __tablename__ = "activity"
    _unique_columns = ["label", "project_id", "course_id"]

    id: Mapped[int] = mapped_column(primary_key=True)
    label: Mapped[str] = mapped_column(String(30))
    start: Mapped[int] = mapped_column(Integer, nullable=True)
    duration: Mapped[int] = mapped_column(Integer, nullable=False)
    course_id: Mapped[int] = mapped_column(ForeignKey("course.id"), nullable=False)
    course: Mapped["Course"] = relationship("Course", back_populates="activities")
    earliest_start_slot: Mapped[int] = mapped_column(Integer, nullable=True)
    latest_start_slot: Mapped[int] = mapped_column(Integer, nullable=True)
    kind_id: Mapped[int] = mapped_column(ForeignKey("activity_kind.id"))
    kind: Mapped["ActivityKind"] = relationship("ActivityKind")
    students_id: Mapped[int] = mapped_column(ForeignKey("students_group.id"))
    students: Mapped["StudentsGroup"] = relationship(back_populates="activities")
    project_id: Mapped[int] = mapped_column(ForeignKey("project.id"))
    project: Mapped["Project"] = relationship(back_populates="activities")

    # ROOMS
    room_pool: Mapped[List["Room"]] = relationship(
        secondary=activity_room_pool_association_table,
        back_populates="activities_pools",
    )
    room_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    allocated_rooms: Mapped[List["Room"]] = relationship(
        secondary=activity_room_allocation_association_table,
        back_populates="activities_allocations",
    )
    # TEACHER
    teacher_pool: Mapped[List["Teacher"]] = relationship(
        secondary=activity_teacher_pool_association_table,
        back_populates="activities_pools",
    )
    teacher_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    allocated_teachers: Mapped[List["Teacher"]] = relationship(
        secondary=activity_teacher_allocation_association_table,
        back_populates="activities_allocations",
    )

    activities_groups: Mapped[List["ActivityGroup"]] = relationship(
        secondary=activity_groups_association_table,
        back_populates="activities",
    )
    __table_args__ = (UniqueConstraint(*_unique_columns, name="_unique_activity"),)

    def __repr__(self) -> str:
        name = self.__class__.__name__
        return f"<{name}: id={self.id}, label={self.label}, kind={self.kind.label}, course={self.course.label}, start={self.start}, duration={self.duration}>"

    @property
    def earliest_start(self):
        slot = self.earliest_start_slot
        if slot == None:
            return None
        return self.project.slots_to_datetime(slot)

    @property
    def latest_start(self):
        slot = self.latest_start_slot
        if slot == None:
            return None
        return self.project.slots_to_datetime(slot)

    @property
    def end(self):
        return self.start + self.duration

    @property
    def start_datetime(self):
        return self.project.slots_to_datetime(self.start)

    @property
    def end_datetime(self):
        return self.project.slots_to_datetime(self.end)

    @property
    def duration_timedelta(self):
        return self.project.slots_to_duration(self.duration)

    @property
    def ressources_to_series(self):
        out = {
            "id": self.id,
            "label": self.label,
            "kind": self.kind.label,
            "duration": self.project.slots_to_duration(self.duration).to_str(),
            "students": self.students.label,
            "teacher_pool": ", ".join([t.full_name for t in self.teacher_pool]),
            "teacher_count": self.teacher_count,
            "room_pool": ", ".join([r.label for r in self.room_pool]),
            "room_count": self.room_count,
            "latest_start": self.latest_start,
            "earliest_start": self.earliest_start,
            "start": self.start_datetime,
        }
        return pd.Series(out)

    @property
    def planification_to_series(self):
        start = self.start_datetime
        end = self.end_datetime
        start_isocalendar = start.isocalendar()
        week = start_isocalendar.week
        weekday = start_isocalendar.weekday
        year = start_isocalendar.year
        start_clock = f"{start.hour:02d}:{start.minute:02d}"
        end_clock = f"{end.hour:02d}:{end.minute:02d}"
        duration = self.duration_timedelta.to_str()
        out = {
            "id": self.id,
            "label": self.label,
            "kind": self.kind.label,
            "start_slot": self.start,
            "year": year,
            "week": week,
            "weekday": weekday,
            "start": start_clock,
            "end": end_clock,
            "duration": duration,
            "students": self.students.label,
            "allocated_teachers": ", ".join(
                [t.full_name for t in self.allocated_teachers]
            ),
            "allocated_rooms": ", ".join([r.label for r in self.allocated_rooms]),
            "teacher_pool": ", ".join([t.full_name for t in self.teacher_pool]),
            "teacher_count": self.teacher_count,
            "room_pool": ", ".join([r.label for r in self.room_pool]),
            "room_count": self.room_count,
        }
        return pd.Series(out)


class Course(Base):
    __tablename__ = "course"
    _unique_columns = ["label"]

    id: Mapped[int] = mapped_column(primary_key=True)
    label: Mapped[str] = mapped_column(String(30), unique=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("project.id"))
    project: Mapped["Project"] = relationship(back_populates="courses")
    # manager_id: Mapped[int] = mapped_column(ForeignKey("teacher.id"))
    # manager: Mapped["Teacher"] = relationship(back_populates="managed_courses")
    # planner_id: Mapped[int] = mapped_column(ForeignKey("teacher.id"))
    # planner: Mapped["Teacher"] = relationship(back_populates="planned_courses")
    manager_id: Mapped[int] = mapped_column(ForeignKey("manager.id"))
    manager: Mapped["Manager"] = relationship(back_populates="courses")
    planner_id: Mapped[int] = mapped_column(ForeignKey("planner.id"))
    planner: Mapped["Planner"] = relationship(back_populates="courses")

    activities: Mapped[List["Activity"]] = relationship(
        "Activity", back_populates="course"
    )
    activity_groups: Mapped[List["ActivityGroup"]] = relationship(
        "ActivityGroup", back_populates="course"
    )

    def __repr__(self) -> str:
        name = self.__class__.__name__
        return (
            f"<{name}: id={self.id}, label={self.label}, manager={self.manager.label}>"
        )

    @property
    def activity_graph(self):
        G = nx.DiGraph()

        ag = self.activity_groups
        # print(ag)
        project = self.project
        for group in ag:
            group_label = group.label
            G.add_node(group_label)
        for group in ag:
            group_label = group.label
            for sa in group.starts_after:
                og = sa.to_activity_group
                ol = og.label
                G.add_edge(group_label, ol)
                min_offset_slots = sa.min_offset
                max_offset_slots = sa.max_offset
                min_offset = project.slots_to_duration(min_offset_slots)
                max_offset = project.slots_to_duration(max_offset_slots)
                G.edges[group_label, ol]["min_offset_slots"] = min_offset_slots
                G.edges[group_label, ol]["max_offset_slots"] = max_offset_slots
                G.edges[group_label, ol]["min_offset"] = min_offset
                G.edges[group_label, ol]["max_offset"] = max_offset
        return G


class ActivityGroup(Base):
    __tablename__ = "activity_group"
    _unique_columns = ["label", "course_id"]

    id: Mapped[int] = mapped_column(primary_key=True)
    label: Mapped[str] = mapped_column(String(30), unique=False)
    course_id: Mapped[int] = mapped_column(ForeignKey("course.id"), nullable=False)
    course: Mapped["Course"] = relationship(back_populates="activity_groups")
    project_id: Mapped[int] = mapped_column(ForeignKey("project.id"))
    project: Mapped["Project"] = relationship(back_populates="activity_groups")

    activities: Mapped[List["Activity"]] = relationship(
        secondary=activity_groups_association_table,
        back_populates="activities_groups",
    )

    starts_after: Mapped[List["StartsAfterConstraint"]] = relationship(
        foreign_keys="StartsAfterConstraint.from_activity_group_id",
        back_populates="from_activity_group",
    )
    is_before: Mapped[List["StartsAfterConstraint"]] = relationship(
        foreign_keys="StartsAfterConstraint.to_activity_group_id",
        back_populates="to_activity_group",
    )

    __table_args__ = (UniqueConstraint(*_unique_columns, name="_unique_activity"),)

    def __repr__(self) -> str:
        name = self.__class__.__name__
        nact = len(self.activities)
        return f"<{name}: id={self.id}, label={self.label}, course={self.course} with {nact} activities >"


class Room(Base):
    __tablename__ = "room"
    _unique_columns = ["label"]

    id: Mapped[int] = mapped_column(primary_key=True)
    label: Mapped[str] = mapped_column(String(30), unique=True)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    project_id: Mapped[int] = mapped_column(ForeignKey("project.id"))
    project: Mapped["Project"] = relationship(back_populates="rooms")
    activities_pools: Mapped[List["Activity"]] = relationship(
        secondary=activity_room_pool_association_table, back_populates="room_pool"
    )
    activities_allocations: Mapped[List["Activity"]] = relationship(
        secondary=activity_room_allocation_association_table,
        back_populates="allocated_rooms",
    )
    static_activities_allocations: Mapped[List["StaticActivity"]] = relationship(
        secondary=static_activity_room_allocation_association_table,
        back_populates="allocated_rooms",
    )
    __table_args__ = (UniqueConstraint(*_unique_columns, name="_unique_room"),)

    def __repr__(self) -> str:
        name = self.__class__.__name__
        return f"<{name}: id={self.id}, label={self.label}, capacity={self.capacity}>"


# WIP
class ActivityKind(Base):
    __tablename__ = "activity_kind"
    _unique_columns = ["label"]

    id: Mapped[int] = mapped_column(primary_key=True)
    label: Mapped[str] = mapped_column(String(30), unique=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("project.id"))
    project: Mapped["Project"] = relationship(back_populates="activity_kinds")
    activities: Mapped[List["Activity"]] = relationship(back_populates="kind")

    allowed_daily_start_slots: Mapped[List["DailySlot"]] = relationship(
        secondary=activity_kind_daily_slots_association_table,
        back_populates="allowed_by",
    )

    def __repr__(self) -> str:
        name = self.__class__.__name__
        return f"<{name}: id={self.id}, label={self.label}>"


class DailySlot(Base):
    __tablename__ = "daily_slot"
    _unique_columns = ["label", "project_id"]

    id: Mapped[int] = mapped_column(primary_key=True)
    label: Mapped[str] = mapped_column(String(30), unique=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("project.id"))
    project: Mapped["Project"] = relationship(back_populates="daily_slots")
    week_slots_availability: Mapped[List["WeekSlotsAvailabiblity"]] = relationship(
        back_populates="daily_slot"
    )

    allowed_by: Mapped[List["ActivityKind"]] = relationship(
        secondary=activity_kind_daily_slots_association_table,
        back_populates="allowed_daily_start_slots",
    )

    def __repr__(self) -> str:
        name = self.__class__.__name__
        return f"<{name}: id={self.id}, label={self.label}>"


class WeekDay(Base):
    __tablename__ = "week_day"
    _unique_columns = ["label"]
    project_id: Mapped[int] = mapped_column(ForeignKey("project.id"))
    project: Mapped["Project"] = relationship(back_populates="week_days")

    id: Mapped[int] = mapped_column(primary_key=True)
    label: Mapped[str] = mapped_column(String(30), unique=True)
    week_slots_availability: Mapped[List["WeekSlotsAvailabiblity"]] = relationship(
        back_populates="week_day"
    )

    def __repr__(self) -> str:
        name = self.__class__.__name__
        return f"<{name}: id={self.id}, label={self.label}>"


class WeekSlotsAvailabiblity(Base):
    __tablename__ = "week_structure"
    _unique_columns = ["project_id", "week_day_id", "daily_slot_id"]

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("project.id"))
    project: Mapped["Project"] = relationship(back_populates="week_slots_availability")
    week_day_id: Mapped[int] = mapped_column(ForeignKey("week_day.id"))
    week_day: Mapped["WeekDay"] = relationship(back_populates="week_slots_availability")
    daily_slot_id: Mapped[int] = mapped_column(ForeignKey("daily_slot.id"))
    daily_slot: Mapped["DailySlot"] = relationship(
        back_populates="week_slots_availability"
    )
    available: Mapped[bool] = mapped_column(Boolean, nullable=False)

    __table_args__ = (
        UniqueConstraint(*_unique_columns, name="_unique_week_structure"),
    )

    def __repr__(self) -> str:
        name = self.__class__.__name__
        wd = self.week_day.label
        ds = self.daily_slot.id
        return f"<{name}: id={self.id}, week_day={wd}, daily_slot={ds}, available={self.available}>"


class Teacher(Base):
    __tablename__ = "teacher"
    _unique_columns = ["label"]

    id: Mapped[int] = mapped_column(primary_key=True)
    label: Mapped[str] = mapped_column(String(30), unique=True)
    full_name: Mapped[str] = mapped_column(String(50), nullable=True)
    email: Mapped[str] = mapped_column(String(50), nullable=True)
    # managed_courses: Mapped[List["Course"]] = relationship(back_populates="manager")
    # planned_courses: Mapped[List["Course"]] = relationship(back_populates="planner")
    project_id: Mapped[int] = mapped_column(ForeignKey("project.id"))
    project: Mapped["Project"] = relationship(back_populates="teachers")

    activities_pools: Mapped[List["Activity"]] = relationship(
        secondary=activity_teacher_pool_association_table, back_populates="teacher_pool"
    )
    activities_allocations: Mapped[List["Activity"]] = relationship(
        secondary=activity_teacher_allocation_association_table,
        back_populates="allocated_teachers",
    )
    static_activities_allocations: Mapped[List["StaticActivity"]] = relationship(
        secondary=static_activity_teacher_allocation_association_table,
        back_populates="allocated_teachers",
    )
    __table_args__ = (UniqueConstraint(*_unique_columns, name="_unique_teacher"),)

    def __repr__(self) -> str:
        name = self.__class__.__name__
        return f"<{name}: id={self.id}, label={self.label}>"


class Planner(Base):
    __tablename__ = "planner"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("project.id"))
    project: Mapped["Project"] = relationship(back_populates="planners")
    label: Mapped[str] = mapped_column(String(30), unique=True)
    full_name: Mapped[str] = mapped_column(String(50), nullable=False)
    email: Mapped[str] = mapped_column(String(50), nullable=False)
    courses: Mapped[List["Course"]] = relationship(back_populates="planner")


class Manager(Base):
    __tablename__ = "manager"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("project.id"))
    project: Mapped["Project"] = relationship(back_populates="managers")
    label: Mapped[str] = mapped_column(String(30), unique=True)
    full_name: Mapped[str] = mapped_column(String(50), nullable=False)
    email: Mapped[str] = mapped_column(String(50), nullable=False)
    courses: Mapped[List["Course"]] = relationship(back_populates="manager")


class StartsAfterConstraint(Base):
    __tablename__ = "starts_after_constraint"
    _unique_columns = [
        "label",
        "project_id",
        "from_activity_group_id",
        "to_activity_group_id",
        "min_offset",
    ]
    __table_args__ = (
        UniqueConstraint(*_unique_columns, name="_unique_starts_after_constraints"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    label: Mapped[str] = mapped_column(String(30), nullable=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("project.id"))
    min_offset: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_offset: Mapped[int] = mapped_column(Integer, nullable=True)
    project: Mapped["Project"] = relationship(back_populates="starts_after_constraints")
    from_activity_group_id: Mapped[int] = mapped_column(ForeignKey("activity_group.id"))
    from_activity_group: Mapped["ActivityGroup"] = relationship(
        "ActivityGroup",
        foreign_keys=[from_activity_group_id],
        back_populates="starts_after",
    )
    to_activity_group_id: Mapped[int] = mapped_column(ForeignKey("activity_group.id"))
    to_activity_group: Mapped["ActivityGroup"] = relationship(
        "ActivityGroup", foreign_keys=[to_activity_group_id], back_populates="is_before"
    )

    def __repr__(self) -> str:
        name = self.__class__.__name__
        from_label = self.from_activity_group.label
        to_label = self.to_activity_group.label
        return f"<{name}: id={self.id}, label={self.label}, min_offset={self.min_offset}, max_offset={self.max_offset}, from={from_label}, to={to_label}>"
