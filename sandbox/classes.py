from typing import List
from typing import Optional
from sqlalchemy import ForeignKey
from sqlalchemy import String, Integer, Boolean, UniqueConstraint, Column, Table
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError


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

student_atomic_groups_association_table = Table(
    "student_atomic_groups_association_table",
    Base.metadata,
    Column("atom_id", ForeignKey("atomic_student.id"), primary_key=True),
    Column("group_id", ForeignKey("students_group.id"), primary_key=True),
)


class AtomicStudent(Base):
    __tablename__ = "atomic_student"
    _unique_columnns = ["label"]

    id: Mapped[int] = mapped_column(primary_key=True)
    label: Mapped[str] = mapped_column(String(30), unique=True)

    __table_args__ = (
        UniqueConstraint(*_unique_columnns, name="_unique_atomic_student"),
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
    _unique_columnns = ["label"]

    id: Mapped[int] = mapped_column(primary_key=True)
    label: Mapped[str] = mapped_column(String(30), unique=True)

    __table_args__ = (
        UniqueConstraint(*_unique_columnns, name="_unique_student_groups"),
    )

    students: Mapped[List["AtomicStudent"]] = relationship(
        secondary=student_atomic_groups_association_table,
        back_populates="groups",
    )

    activities: Mapped[List["Activity"]] = relationship(
        "Activity", back_populates="students"
    )

    def __repr__(self) -> str:
        name = self.__class__.__name__
        return f"<{name}: id={self.id}, label={self.label}>"


class Activity(Base):
    __tablename__ = "activity"
    _unique_columnns = ["course", "label"]

    id: Mapped[int] = mapped_column(primary_key=True)
    label: Mapped[str] = mapped_column(String(30))
    start: Mapped[int] = mapped_column(Integer, nullable=True)
    duration: Mapped[int] = mapped_column(Integer, nullable=False)
    tunable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    course: Mapped[str] = mapped_column(String(30), nullable=False)
    kind: Mapped[str] = mapped_column(String(30))
    students_id: Mapped[int] = mapped_column(ForeignKey("students_group.id"))
    students: Mapped["StudentsGroup"] = relationship(back_populates="activities")

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

    __table_args__ = (UniqueConstraint(*_unique_columnns, name="_unique_activity"),)

    def __repr__(self) -> str:
        name = self.__class__.__name__
        return f"<{name}: id={self.id}, name={self.label}, kind={self.kind}, course={self.course}, start={self.start}, duration={self.duration},tunable:{self.tunable} >"

    @classmethod
    def get_or_create(cls, session, **kwargs):
        instance = session.query(cls).filter_by(**kwargs).first()
        if instance:
            return instance
        else:
            instance = cls(**kwargs)
            session.add(instance)
            session.commit()
            return instance


class Room(Base):
    __tablename__ = "room"
    _unique_columnns = ["label"]

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
    __table_args__ = (UniqueConstraint(*_unique_columnns, name="_unique_room"),)

    def __repr__(self) -> str:
        name = self.__class__.__name__
        return f"<{name}: id={self.id}, label={self.label}, capacity={self.capacity}>"


class Teacher(Base):
    __tablename__ = "teacher"
    _unique_columnns = ["label"]

    id: Mapped[int] = mapped_column(primary_key=True)
    label: Mapped[str] = mapped_column(String(30), unique=True)

    activities_pools: Mapped[List["Activity"]] = relationship(
        secondary=activity_teacher_pool_association_table, back_populates="teacher_pool"
    )
    activities_allocations: Mapped[List["Activity"]] = relationship(
        secondary=activity_teacher_allocation_association_table,
        back_populates="allocated_teachers",
    )
    __table_args__ = (UniqueConstraint(*_unique_columnns, name="_unique_teacher"),)

    def __repr__(self) -> str:
        name = self.__class__.__name__
        return f"<{name}: id={self.id}, label={self.label}>"
