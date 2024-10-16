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
    WeekStructure,
)
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
import yaml
import os
import numpy as np
from automatic_university_scheduler.datetimeutils import DateTime as DT
from automatic_university_scheduler.datetimeutils import datetime_to_slot, TimeDelta
from automatic_university_scheduler.scheduling import load_setup, read_json_data
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


setup = yaml.safe_load(open("setup.yaml"))
engine = create_engine(setup["engine"], echo=False)
Base.metadata.create_all(engine)

project_data_folder = setup["project_data_folder"]
courses_data_folder = setup["courses_data_folder"]
courses_data_files = [f for f in os.listdir(courses_data_folder) if f.endswith(".yaml")]


session = Session(engine)


project_data = load_setup(os.path.join(project_data_folder, "setup.yaml"))
students_data = yaml.safe_load(
    open(os.path.join(project_data_folder, "student_data.yaml"))
)
teachers_data = yaml.safe_load(
    open(os.path.join(project_data_folder, "teacher_data.yaml"))
)

WEEK_STRUCTURE = project_data["WEEK_STRUCTURE"]
ORIGIN_DATETIME = project_data["ORIGIN_DATETIME"]
HORIZON = project_data["HORIZON"]
TIME_SLOT_DURATION = project_data["TIME_SLOT_DURATION"]
MAX_WEEKS = project_data["MAX_WEEKS"]


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
daily_slots = create_daily_slots(session, project, TIME_SLOT_DURATION)

# WEEK STRUCTURE
week_structure = create_week_structure(
    session, project, project_data, daily_slots, week_days
)

# ACTITVITY KINDS
activity_kinds = create_activity_kinds(session, project, project_data, daily_slots)


# STUDENTS
print("Creating students:")
atomic_students, students_groups = create_students(
    session,
    project,
    students_data,
    origin_datetime=ORIGIN_DATETIME,
    time_slot_duration=TIME_SLOT_DURATION,
    horizon=HORIZON,
)
print("\tStudents groups:\n", *[f"\t\t{s}\n" for s in students_groups.keys()])
print("\tAtomic students:\n", *[f"\t\t{s}\n" for s in atomic_students.keys()])

# TEACHERS
teachers, teachers_unavailable_static_activities = create_teachers(
    session,
    project,
    teachers_data,
    origin_datetime=ORIGIN_DATETIME,
    time_slot_duration=TIME_SLOT_DURATION,
    horizon=HORIZON,
)


courses_data = {}
for file in courses_data_files:
    print("Loading data from", file)
    courses_data.update(yaml.safe_load(open(os.path.join(courses_data_folder, file))))

activities_dic, activities_groups_dic, rooms = create_activities_and_rooms(
    session,
    project,
    courses_data,
    teachers=teachers,
    students_groups=students_groups,
    activity_kinds=activity_kinds,
)

session.commit()
