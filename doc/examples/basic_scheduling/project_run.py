from automatic_university_scheduler.database import Base, Project, StaticActivity
from automatic_university_scheduler.optimize import (
    absolute_week_duration_deviation,
    delete_imported_static_activities,
    SolutionPrinter,
    create_activities_variables,
    create_allowed_time_slots_per_kind,
    create_static_activities_overlap_constraints,
    create_weekly_unavailability_constraints,
)
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
import yaml
from ortools.sat.python import cp_model
import itertools
import numpy as np
from automatic_university_scheduler.datetimeutils import DateTime as DT
from automatic_university_scheduler.utils import Messages, create_instance
from automatic_university_scheduler.preprocessing import extract_constraints_from_table
import time
import pandas as pd
from scipy import ndimage


# SETUP
setup = yaml.safe_load(open("setup.yaml"))
engine = create_engine(setup["engine"], echo=False)
Base.metadata.create_all(engine)
session = Session(engine)

# DATA GATHERING
project = session.execute(select(Project)).scalars().first()


# OR-TOOLS MODEL CREATION
model = cp_model.CpModel()

# STATIC ACTIVITIES
delete_imported_static_activities(session)

path = "filtered_data.csv"
existing_activities_dir = "existing_activities/extractions/"

if path.endswith(".xlsx"):
    raw_data = pd.read_excel(f"{existing_activities_dir}{path}", header=0)
elif path.endswith(".csv"):
    raw_data = pd.read_csv(f"{existing_activities_dir}{path}", header=0)
else:
    raise ValueError("Invalid file format")
(
    constraints,
    ignored_ressources,
    tracked_ressources,
    static_activities_kwargs,
) = extract_constraints_from_table(raw_data, project)

# Adding Imported Static Activities
for kwargs in static_activities_kwargs:
    create_instance(session, StaticActivity, **kwargs)

# FRESHLY UPDATED STATIC ACTIVITIES
static_activities = project.static_activities


# INTERVALS CREATION
(
    activities_intervals,
    activities_starts,
    activities_ends,
    activities_durations,
    atomic_students_intervals,
    room_intervals,
    teacher_intervals,
    activities_alternative_ressources,
) = create_activities_variables(model, project)

# ALLOWED TIME SLOTS PER KIND
create_allowed_time_slots_per_kind(model, project, activities_starts)

# STATIC ACTIVITIES OVERLAP CONSTRAINTS
(
    atomic_students_static_intervals,
    teacher_static_intervals,
    room_static_intervals,
) = create_static_activities_overlap_constraints(
    project, atomic_students_intervals, teacher_intervals, room_intervals, model
)

# WEEKLY UNAVAILABILITY CONSTRAINTS
create_weekly_unavailability_constraints(project, model, atomic_students_intervals)

# OBJECTIVE FUNCTION
value = absolute_week_duration_deviation(
    project, model, activities_starts, activities_durations
)
model.Minimize(value)


# CHECK MODEL INTEGRITY
print("CHECK MODEL INTEGRITY")
out = model.Validate()
if out == "":
    print(f"  => Model is  valid: {Messages.SUCCESS}")
else:
    print(f"Model is not valid: {Messages.ERROR}")
    print(out)


# Solve model
print("SOLVING ...")
solver = cp_model.CpSolver()
solver.parameters.max_time_in_seconds = 120  # 54000 = 15h
solver.parameters.num_search_workers = 8
# solver.parameters.log_search_progress = True
# solver.fix_variables_to_their_hinted_value = True


solution_printer = SolutionPrinter(limit=25)  # 30 is OK
t0 = time.time()
status = solver.Solve(model, solution_printer)
solver_final_status = solver.StatusName()
print(f"SOLVER STATUS: {solver_final_status}")
t1 = time.time()
print(solver.ResponseStats())
print(f"Elapsed time: {t1-t0:.2f} s")

setup = project.setup
if not solver_final_status == "INFEASIBLE":
    print(f"  => Solution found: {Messages.SUCCESS}")
    activities_dic = {a.id: a for a in project.activities}
    for aid, start in activities_starts.items():
        start_slot = solver.Value(start)
        alabel = activities_dic[aid].label
        activity = activities_dic[aid]
        clabel = activity.course.label
        activity.start = start_slot
        start_datetime = activity.start_datetime
        activity_alternative_ressources = activities_alternative_ressources[aid]
        activity.allocated_rooms = []
        for existance, alt_rooms in activity_alternative_ressources["rooms"]:
            if solver.Value(existance) == 1:
                for room in alt_rooms:
                    activity.allocated_rooms.append(room)

        activity.allocated_teachers = []
        for existance, alt_teachers in activity_alternative_ressources["teachers"]:
            if solver.Value(existance) == 1:
                for teacher in alt_teachers:
                    activity.allocated_teachers.append(teacher)
        allocated_rooms_labels = [r.label for r in activity.allocated_rooms]
        allocated_teachers_labels = [t.full_name for t in activity.allocated_teachers]
        print(
            f"Activity {aid} ({clabel}/{alabel}) starts at {start_slot} = {start_datetime} in rooms {allocated_rooms_labels} with teachers {allocated_teachers_labels}"
        )

        session.commit()
# session.close()
