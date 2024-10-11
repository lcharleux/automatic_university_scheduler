from classes import Base, Room, Activity, Teacher, AtomicStudent, StudentsGroup
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
import yaml
import os
import numpy as np


class Model:
    def __init__(self, engine):
        self.engine = engine


def get_or_create(session, cls, commit=False, **kwargs):
    unique_columns = cls._unique_columnns
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
rooms_labels = set()
teachers_labels = set()
atomic_students_labels = set()
students_groups_labels = set()


session = Session(engine)
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
        session, AtomicStudent, label=label, commit=True
    )

for label in sorted(list(students_groups_labels)):
    students = np.array(
        [atomic_students[label] for label in students_data["groups"][label]]
    )
    labs = [s.label for s in students]
    students = (students[np.argsort(labs)]).tolist()
    students_groups[label] = get_or_create(
        session, StudentsGroup, label=label, students=students, commit=True
    )

for label in sorted(list(rooms_labels)):
    rooms[label] = get_or_create(session, Room, label=label, capacity=30, commit=True)

for label in sorted(list(teachers_labels)):
    teachers[label] = get_or_create(session, Teacher, label=label, commit=True)

print("gathered rooms", rooms.keys())

# activities = (
# session.execute(select(Activity)).scalars().all()
# )

for course, course_data in data.items():
    activities = course_data["activities"]
    for activity, activity_data in activities.items():
        print("Creating activity", activity)
        activity_args = {"label": activity, "course": course}
        activity_args["kind"] = activity_data["kind"]
        activity_args["duration"] = activity_data["duration"]
        activity_args["room_pool"] = [rooms[l] for l in activity_data["rooms"]["pool"]]
        activity_args["teacher_pool"] = [
            teachers[l] for l in activity_data["teachers"]["pool"]
        ]
        activity_args["students"] = students_groups[activity_data["students"]]
        # new_activity = Activity(**activity_args)
        new_activity = get_or_create(session, Activity, **activity_args, commit=True)

session.commit()
