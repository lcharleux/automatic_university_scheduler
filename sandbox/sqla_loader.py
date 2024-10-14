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
)
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
import yaml
import os
import numpy as np
from automatic_university_scheduler.datetime import DateTime as DT
from automatic_university_scheduler.datetime import datetime_to_slot
from automatic_university_scheduler.scheduling import load_setup, read_json_data
import math


def process_constraint_static_activity(
    constraint, origin_datetime, time_slot_duration, out=None
):
    """
    Process a constraint and return a dictionary with the necessary information to create a StaticActivity object.
    """
    if out == None:
        out = {}
    start = datetime_to_slot(
        DT.from_str(constraint["start"]),
        origin_datetime=origin_datetime,
        slot_duration=time_slot_duration,
        round="floor",
    )
    end = datetime_to_slot(
        DT.from_str(constraint["end"]),
        origin_datetime=origin_datetime,
        slot_duration=time_slot_duration,
        round="ceil",
    )
    duration = end - start
    out["start"] = start
    out["duration"] = duration
    return out


def get_or_create(session, cls, commit=False, **kwargs):
    if hasattr(cls, "_unique_columns"):
        unique_columns = cls._unique_columns
        cropped_kwargs = {k: v for k, v in kwargs.items() if k in unique_columns}
        instance = session.query(cls).filter_by(**cropped_kwargs).first()
        if instance:

            return instance
        else:
            instance = cls(**kwargs)
            session.add(instance)
            if commit:
                session.commit()
            return instance
    else:
        instance = cls(**kwargs)
        session.add(instance)
        if commit:
            session.commit()
        return instance


setup = yaml.safe_load(open("setup.yaml"))
engine = create_engine(setup["engine"], echo=False)
Base.metadata.create_all(engine)

project_data_folder = setup["project_data_folder"]


courses_data_folder = setup["courses_data_folder"]
courses_data_files = [f for f in os.listdir(courses_data_folder) if f.endswith(".yaml")]


data = {}
# RESSOURCES
rooms = {}
teachers = {}
atomic_students = {}
students_groups = {}
activities_dic = {}
activities_groups_dic = {}
rooms_labels = set()
teachers_labels = set()
atomic_students_labels = set()
students_groups_labels = set()


session = Session(engine)


project_data = load_setup(os.path.join(project_data_folder, "setup.yaml"))
WEEK_STRUCTURE = project_data["WEEK_STRUCTURE"]
ORIGIN_DATETIME = project_data["ORIGIN_DATETIME"]
HORIZON = project_data["HORIZON"]
TIME_SLOT_DURATION = project_data["TIME_SLOT_DURATION"]
MAX_WEEKS = project_data["MAX_WEEKS"]


project = get_or_create(
    session,
    Project,
    label="project",
    origin_datetime=ORIGIN_DATETIME,
    horizon=HORIZON,
    commit=True,
)


print("Loading students data:")
students_data = yaml.safe_load(
    open(os.path.join(project_data_folder, "student_data.yaml"))
)
for group, group_data in students_data["groups"].items():
    students_groups_labels.add(group)
    atomic_students_labels.update(group_data)


print("Loading data from files:")
for file in courses_data_files:
    print("Loading data from", file)
    data.update(yaml.safe_load(open(os.path.join(courses_data_folder, file))))

print("Creating rooms and teachers:")
for course, course_data in data.items():
    activities = course_data["activities"]
    for activity, activity_data in activities.items():
        room_pool = activity_data["rooms"]["pool"]
        teacher_pool = activity_data["teachers"]["pool"]
        rooms_labels.update(room_pool)
        teachers_labels.update(teacher_pool)

for label in sorted(list(atomic_students_labels)):
    atomic_students[label] = get_or_create(
        session, AtomicStudent, label=label, project=project, commit=True
    )

for label in sorted(list(students_groups_labels)):
    students = np.array(
        [atomic_students[label] for label in students_data["groups"][label]]
    )
    labs = [s.label for s in students]
    students = (students[np.argsort(labs)]).tolist()
    students_groups[label] = get_or_create(
        session,
        StudentsGroup,
        label=label,
        students=students,
        project=project,
        commit=True,
    )


for group_label, group_data in students_data["constraints"].items():
    group = students_groups[group_label]
    if "unavailable" in group_data.keys():
        unvailable_data = group_data["unavailable"]
        for constraint in unvailable_data:
            print("Creating constraint", constraint)
            if constraint["kind"] == "datetime":
                static_activity_kwargs = {
                    "project": project,
                    "kind": "students unavailable",
                    "students": group,
                    "label": "unavailable",
                }
                print("Processing constraint", static_activity_kwargs)
                static_activity_kwargs = process_constraint_static_activity(
                    constraint=constraint,
                    origin_datetime=ORIGIN_DATETIME,
                    time_slot_duration=TIME_SLOT_DURATION,
                    out=static_activity_kwargs,
                )
                get_or_create(
                    session, StaticActivity, **static_activity_kwargs, commit=True
                )


for label in sorted(list(rooms_labels)):
    rooms[label] = get_or_create(session, Room, label=label, capacity=30, commit=True)

for label in sorted(list(teachers_labels)):
    teachers[label] = get_or_create(session, Teacher, label=label, commit=True)

print("gathered rooms", rooms.keys())

# activities = (
# session.execute(select(Activity)).scalars().all()
# )


for course_label, course_data in data.items():
    activities = course_data["activities"]
    for activity_label, activity_data in activities.items():
        print("Creating activity", activity_label)
        activity_args = {
            "label": activity_label,
            "course": course_label,
            "project": project,
        }
        activity_args["kind"] = activity_data["kind"]
        activity_args["duration"] = activity_data["duration"]
        activity_args["room_pool"] = [rooms[l] for l in activity_data["rooms"]["pool"]]
        activity_args["teacher_pool"] = [
            teachers[l] for l in activity_data["teachers"]["pool"]
        ]
        activity_args["students"] = students_groups[activity_data["students"]]
        # new_activity = Activity(**activity_args)
        new_activity = get_or_create(session, Activity, **activity_args, commit=True)
        activities_dic[(course_label, activity_label)] = new_activity
    for group_label, group_data in course_data["inner_activity_groups"].items():
        print("Creating activity group", group_label)
        gra = [activities_dic[(course, l)] for l in group_data]
        activity_group_kwargs = {
            "label": group_label,
            "activities": gra,
            "project": project,
            "course": course_label,
        }
        new_activity_group = get_or_create(
            session, ActivityGroup, **activity_group_kwargs, commit=True
        )
        activities_groups_dic[(course_label, group_label)] = new_activity_group


session.commit()
