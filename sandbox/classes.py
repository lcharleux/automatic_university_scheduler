from typing import List
from typing import Optional
from sqlalchemy import ForeignKey
from sqlalchemy import (
    String,
    Integer,
    Boolean,
    UniqueConstraint,
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
from automatic_university_scheduler.datetime import DateTime as DT


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


class Project(Base):
    __tablename__ = "project"
    _unique_columns = ["label"]

    id: Mapped[int] = mapped_column(primary_key=True)
    label: Mapped[str] = mapped_column(String(30), unique=True)
    description: Mapped[str] = mapped_column(String(255), nullable=True)
    origin_datetime: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    horizon: Mapped[int] = mapped_column(Integer, nullable=False)
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
    activitiy_groups: Mapped[List["ActivityGroup"]] = relationship(
        "ActivityGroup", back_populates="project"
    )
    starts_after_constraints: Mapped[List["StartsAfterConstraint"]] = relationship(
        "StartsAfterConstraint", back_populates="project"
    )

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
    students_id: Mapped[int] = mapped_column(ForeignKey("students_group.id"))
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


class Activity(Base):
    __tablename__ = "activity"
    _unique_columns = ["course", "label", "project_id"]

    id: Mapped[int] = mapped_column(primary_key=True)
    label: Mapped[str] = mapped_column(String(30))
    start: Mapped[int] = mapped_column(Integer, nullable=True)
    duration: Mapped[int] = mapped_column(Integer, nullable=False)
    tunable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    course: Mapped[str] = mapped_column(String(30), nullable=False)
    kind: Mapped[str] = mapped_column(String(30))
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
        return f"<{name}: id={self.id}, label={self.label}, kind={self.kind}, course={self.course}, start={self.start}, duration={self.duration}>"


class ActivityGroup(Base):
    __tablename__ = "activity_group"
    _unique_columns = ["label", "course"]

    id: Mapped[int] = mapped_column(primary_key=True)
    label: Mapped[str] = mapped_column(String(30), unique=True)
    course: Mapped[str] = mapped_column(String(30), nullable=False)
    project_id: Mapped[int] = mapped_column(ForeignKey("project.id"))
    project: Mapped["Project"] = relationship(back_populates="activitiy_groups")

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


class Teacher(Base):
    __tablename__ = "teacher"
    _unique_columns = ["label"]

    id: Mapped[int] = mapped_column(primary_key=True)
    label: Mapped[str] = mapped_column(String(30), unique=True)

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


class StartsAfterConstraint(Base):
    __tablename__ = "starts_after_constraint"
    _unique_columns = [
        "label",
        "project_id",
        "from_activity_group_id",
        "to_activity_group_id",
        "min_offset",
        "max_offset",
    ]

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
