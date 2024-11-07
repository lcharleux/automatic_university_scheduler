from classes import (
    Base,
    Room,
    Activity,
    Teacher,
    AtomicStudent,
    StudentsGroup,
    Project,
    StaticActivity,
    ActivityGroup,
    StartsAfterConstraint,
    DailySlot,
    ActivityKind,
    WeekDay,
    WeekSlotsAvailabiblity,
    load_setup,
)
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
import yaml
import os
import numpy as np
from automatic_university_scheduler.datetimeutils import DateTime as DT
from automatic_university_scheduler.datetimeutils import datetime_to_slot, TimeDelta
from automatic_university_scheduler.scheduling import read_json_data
import math
import itertools
import datetime
from preprocessing import (
    create_students,
    create_daily_slots,
    create_teachers,
    create_activities_and_rooms,
    create_activity_kinds,
    create_week_structure,
    create_weekdays,
)
from db_utils import get_or_create

model = yaml.safe_load(open("model.yaml"))
db_info = yaml.safe_load(open("setup.yaml"))
try:
    os.remove("./data.db")
    print("Database removed")
except:
    print("Database not found and then not removed.")

print("Creating database")
engine = create_engine(db_info["engine"], echo=False)
Base.metadata.create_all(engine)

session = Session(engine)

setup = load_setup(model["setup"])

WEEK_STRUCTURE = setup["WEEK_STRUCTURE"]
ORIGIN_DATETIME = setup["ORIGIN_DATETIME"]
HORIZON = setup["HORIZON"]
TIME_SLOT_DURATION = setup["TIME_SLOT_DURATION"]
# MAX_WEEKS = setup["MAX_WEEKS"]


project = get_or_create(
    session,
    Project,
    label="project",
    time_slot_duration_seconds=TIME_SLOT_DURATION.seconds,
    origin_datetime=ORIGIN_DATETIME,
    horizon=HORIZON,
    commit=True,
)


week_days = create_weekdays(session, project)
# DAILY SLOTS
daily_slots = create_daily_slots(session, project)

# WEEK STRUCTURE
week_structure = create_week_structure(
    session, project, WEEK_STRUCTURE, daily_slots, week_days
)

# ACTITVITY KINDS
activity_kinds = create_activity_kinds(
    session, project, setup["ACTIVITIES_KINDS"], daily_slots
)


# STUDENTS
print("Creating students")
atomic_students, students_groups = create_students(session, project, model["students"])


# TEACHERS
teachers, teachers_unavailable_static_activities = create_teachers(
    session, project, model["teachers"]
)

# ACTIVITIES
(
    activities_dic,
    activities_groups_dic,
    rooms,
    starts_after_constraints,
) = create_activities_and_rooms(
    session,
    project,
    model["courses"],
    teachers=teachers,
    students_groups=students_groups,
    activity_kinds=activity_kinds,
)

session.commit()
