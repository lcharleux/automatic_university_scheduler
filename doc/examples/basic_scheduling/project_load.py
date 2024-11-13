from automatic_university_scheduler.database import (
    Base,
    Project,
)

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
import yaml
import os
import numpy as np
from automatic_university_scheduler.datetimeutils import DateTime as DT
from automatic_university_scheduler.utils import create_instance
from automatic_university_scheduler.preprocessing import (
    load_setup,
    create_students,
    create_daily_slots,
    create_teachers,
    create_activities_and_rooms,
    create_activity_kinds,
    create_week_structure,
    create_weekdays,
    create_managers,
    create_planners,
)
from automatic_university_scheduler.utils import Messages


print(10 * "#" + " LOADING MODEL DATA INTO DATABASE " + 10 * "#")

model = yaml.safe_load(open("model.yaml"))
db_info = yaml.safe_load(open("setup.yaml"))
try:
    os.remove("./data.db")
    print("Database removed", end=" ")
    print(f"=> {Messages.SUCCESS}")
except:
    print("Database not found and then not removed.", "=>", Messages.WARNING)

print("Creating database", end=" ")
engine = create_engine(db_info["engine"], echo=False)
Base.metadata.create_all(engine)
print(f"=> {Messages.SUCCESS}")


session = Session(engine)

setup = load_setup(model["setup"])

WEEK_STRUCTURE = setup["WEEK_STRUCTURE"]
ORIGIN_DATETIME = setup["ORIGIN_DATETIME"]
HORIZON = setup["HORIZON"]
TIME_SLOT_DURATION = setup["TIME_SLOT_DURATION"]


project = create_instance(
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
print("Creating students", end=" ")
atomic_students, students_groups = create_students(session, project, model["students"])
print(f"=> {Messages.SUCCESS}")

# TEACHERS
teachers, teachers_unavailable_static_activities = create_teachers(
    session, project, model["teachers"]
)

# MANAGERS
managers = create_managers(session, project, model["managers"])

# PLANNERS
planners = create_planners(session, project, model["planners"])

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
    room_pools=model["aliases"]["room_pools"],
    teachers=teachers,
    managers=managers,
    planners=planners,
    students_groups=students_groups,
    activity_kinds=activity_kinds,
)

session.commit()
