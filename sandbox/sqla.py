from typing import List
from typing import Optional
from sqlalchemy import ForeignKey
from sqlalchemy import String, Integer, Boolean, UniqueConstraint
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


class ActivityKind(Base):
    __tablename__ = "activity_kind"
    id: Mapped[int] = mapped_column(primary_key=True)
    label: Mapped[str] = mapped_column(String(30))
    activitieszzz: Mapped[List["Activity"]] = relationship(
        "Activity", back_populates="kind"
    )

    def __repr__(self) -> str:
        return f"ActivityKind(id={self.id}, name={self.label})"


class Course(Base):
    __tablename__ = "course"
    id: Mapped[int] = mapped_column(primary_key=True)
    label: Mapped[str] = mapped_column(String(30), unique=True)
    activities: Mapped[List["Activity"]] = relationship(
        "Activity", back_populates="course"
    )

    def __repr__(self) -> str:
        return f"Course(id={self.id}, label={self.label})"


class Activity(Base):
    __tablename__ = "activity"
    id: Mapped[int] = mapped_column(primary_key=True)
    label: Mapped[str] = mapped_column(String(30))
    start: Mapped[int] = mapped_column(Integer, nullable=True)
    duration: Mapped[int] = mapped_column(Integer, nullable=False)
    tunable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("course.id"))
    course: Mapped["Course"] = relationship(back_populates="activities")
    kind_id: Mapped[int] = mapped_column(ForeignKey("activity_kind.id"))
    kind: Mapped["ActivityKind"] = relationship(back_populates="activitieszzz")

    _table_args__ = (UniqueConstraint("course", "label", name="_unique_activity"),)

    def __repr__(self) -> str:
        name = self.__class__.__name__
        return f"<{name}: id={self.id}, name={self.label}, course={self.course.label}, start={self.start}, duration={self.duration},tunable:{self.tunable} >"


engine = create_engine("sqlite:///data.db", echo=False)
Base.metadata.create_all(engine)

# KINDS
CM = ActivityKind(label="CM")
TD = ActivityKind(label="TD")
TP = ActivityKind(label="TP")

# COURSES
Course1 = Course(label="Course1")

# ACTIVITIES
CM1 = Activity(label="CM1", start=None, duration=6, course=Course1, kind=CM)
TD1 = Activity(label="TD1", start=33, duration=6, course=Course1, kind=TD)
TP1 = Activity(label="TP1", start=33, duration=6, course=Course1, kind=TP)


new_items = [Course1, CM1, TD1, TP1]

with Session(engine) as session:
    for item in new_items:
        # if True:
        try:
            session.add(item)
            session.commit()
        except IntegrityError as e:
            session.rollback()
            print(f"Failed to add {item} to the database bacause it alteady exists.")
            print(e)
        except Exception as e:
            raise e

session = Session(engine)

courses = session.execute(select(Course)).scalars()
print("Courses:")
for course in courses:
    print(course)

activities = session.execute(
    select(Activity).where(Activity.label.in_(["CM1", "TD1"]))
).all()
print("Activities:")
for activity in activities:
    print(activity)
