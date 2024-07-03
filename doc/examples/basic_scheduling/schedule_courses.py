import datetime
from ortools.sat.python import cp_model
import numpy as np
from collections import OrderedDict
import itertools
import pandas as pd
import os
from scipy import ndimage
import json
import os
import time
import yaml
import string
from automatic_university_scheduler.scheduling import (
    read_json_data,
    create_unavailable_constraints,
    create_weekly_unavailable_intervals,
    SolutionPrinter,
    export_solution,
    create_activities,
    export_student_schedule_to_xlsx,
    get_absolute_week_duration_deviation,
    read_week_structure,
    load_setup,
    write_student_unavailability_matrices,
    export_modules,
    export_ressources,
)
from automatic_university_scheduler.preprocessing import (
    read_week_structure_from_csv,
    get_unique_ressources_in_activities,
)
from automatic_university_scheduler.utils import (
    read_from_yaml,
    create_directories,
    dump_to_yaml,
    Messages,
)

from automatic_university_scheduler.datetime import (
    DateTime,
    TimeDelta,
    TimeInterval,
    read_time_intervals,
)
import math


# SETUP
setup = load_setup("setup.yaml")
WEEK_STRUCTURE = setup["WEEK_STRUCTURE"]
ORIGIN_DATETIME = setup["ORIGIN_DATETIME"]
HORIZON = setup["HORIZON"]
TIME_SLOT_DURATION = setup["TIME_SLOT_DURATION"]
MAX_WEEKS = setup["MAX_WEEKS"]
TIME_SLOTS_PER_WEEK = setup["TIME_SLOTS_PER_WEEK"]
activities_kinds = setup["ACTIVITIES_KINDS"]
DAYS_PER_WEEK = setup["DAYS_PER_WEEK"]
TIME_SLOTS_PER_DAY = setup["TIME_SLOTS_PER_DAY"]
ORIGIN_MONDAY = setup["ORIGIN_MONDAY"]
HORIZON_MONDAY = setup["HORIZON_MONDAY"]

# ACTIVITY GENERATION

print("Horizon = %i" % HORIZON)

preprocessing_dir = "planification/preprocessing/"
activity_data_dir = "planification/preprocessing/activities/"
output_dir = "planification/outputs/"
extracted_data_dir = "planification/outputs/extracted_data/"
create_directories([activity_data_dir, output_dir, extracted_data_dir])
teacher_data = read_from_yaml("teacher_data.yaml")
activity_data = read_json_data(activity_data_dir)
room_data = read_from_yaml("room_data.yaml")
student_data = read_from_yaml("student_data.yaml")
calendar_data = student_data["constraints"]
if True:
    extracted_constraints = read_from_yaml(
        f"{extracted_data_dir}extracted_constraints.yaml"
    )
    print("Found extracted constraints: " + Messages.SUCCESS)
else:
    extracted_constraints = None
    print("No extracted constraints found: " + Messages.WARNING)

# STUDENTS GROUPS
students_data = yaml.load(open("student_data.yaml"), Loader=yaml.SafeLoader)
students_groups = students_data["groups"]

# MODEL CREATION
model = cp_model.CpModel()


# EXISTING ACTIVITIES

tracked_ressources = read_from_yaml(f"{preprocessing_dir}/tracked_ressources.yaml")
ressource_existing_intervals = {
    k: {t: [] for t in tracked_ressources[k]} for k in ["teachers", "rooms"]
}

# 2. STUDENTS

teacher_data_fullnames = {v["full_name"]: v for k, v in teacher_data.items()}

if extracted_constraints != None:
    for teacher, acts in ressource_existing_intervals["teachers"].items():
        if teacher in extracted_constraints["teachers"].keys():
            teacher_data_fullnames[teacher]["unavailable"] += extracted_constraints[
                "teachers"
            ][teacher]["unavailable"]
            print(f"Added existing constraints for teacher {teacher}")
        else:
            print(f"Teacher {teacher} has no existing constraints.")

    room_data["constraints"] = {
        k: {"unavailable": []} for k in tracked_ressources["rooms"]
    }
    for room, acts in ressource_existing_intervals["rooms"].items():
        if room in extracted_constraints["rooms"].keys():
            room_data["constraints"][room]["unavailable"] += extracted_constraints[
                "rooms"
            ][room]["unavailable"]
            print(f"Added existing constraints for room {room}")
        else:
            print(f"Room {room} has no existing constraints.")

    students_existing_intervals = calendar_data
    for group, existing_constraints in extracted_constraints["students"].items():
        if group not in students_existing_intervals.keys():
            students_existing_intervals[group] = {"unavailable": []}
        if not "unavailable" in students_existing_intervals[group].keys():
            students_existing_intervals[group]["unavailable"] = []
        students_existing_intervals[group]["unavailable"] += existing_constraints[
            "unavailable"
        ]
        print(f"Added extracted constraints for group {group}")

    students_existing_intervals = calendar_data


else:
    print("No extracted constraints found.")
    students_existing_intervals = [calendar_data, calendar_data]  # THIS IS DIRTY

# 4. CHECK STUFF
for teacher, intervals in ressource_existing_intervals["teachers"].items():
    duration = 0
    for interval in intervals:
        start = interval["from_dayslot"]
        end = interval["to_dayslot"]
        start = max(32, start)
        end = min(73, end)
        duration += max(0, end - start)
    print(f"TEACHER {teacher}: cumulated existing activities {duration/4} h")


# TEACHER UNAVAILABILITY
teacher_unavailable_intervals = create_unavailable_constraints(
    model, data=teacher_data_fullnames, start_day=ORIGIN_DATETIME, horizon=HORIZON
)


# ROOM UNAVAILABILITY
room_unavailable_intervals = create_unavailable_constraints(
    model, data=room_data, start_day=ORIGIN_DATETIME, horizon=HORIZON
)

# NIGHT SHIFTS & LUNCH BREAKS AND WEEK-ENDS!
weekly_unavailable_intervals = create_weekly_unavailable_intervals(
    model, WEEK_STRUCTURE, MAX_WEEKS
)

# STUDENT UNAVAILABILITY
# students_data = students_data[:1] # ATTENTION TEST A RETIRER
students_unavailable_intervals = create_unavailable_constraints(
    model,
    data=students_existing_intervals,
    start_day=ORIGIN_DATETIME,
    horizon=HORIZON,
)


# CHECK UNAVAILABILITY
students_atomic_groups = np.unique(
    np.concatenate([v for k, v in students_groups.items()])
)


students_matrices = write_student_unavailability_matrices(
    students_existing_intervals,
    students_atomic_groups,
    students_groups,
    max_weeks=MAX_WEEKS,
    origin_monday=ORIGIN_MONDAY,
    week_structure=WEEK_STRUCTURE,
    time_slot_duration=TIME_SLOT_DURATION,
    output_dir=output_dir,
)
# ACTIVITIES

(
    atomic_students_unavailable_intervals,
    teacher_unavailable_intervals,
    room_unavailable_intervals,
    students_unavailable_intervals,
    weekly_unavailable_intervals,
) = create_activities(
    activity_data,
    model,
    students_groups,
    horizon=HORIZON,
    teacher_unavailable_intervals=teacher_unavailable_intervals,
    room_unavailable_intervals=room_unavailable_intervals,
    students_unavailable_intervals=students_unavailable_intervals,
    weekly_unavailable_intervals=weekly_unavailable_intervals,
    activities_kinds=activities_kinds,
    origin_datetime=ORIGIN_DATETIME,
    slot_duration=TIME_SLOT_DURATION,
)

# COST FUNCTION
makespan = get_absolute_week_duration_deviation(
    model,
    activity_data,
    students_groups,
    students_atomic_groups,
    horizon=HORIZON,
    max_weeks=MAX_WEEKS,
)
model.Minimize(makespan)

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
solver.parameters.num_search_workers = 16
# solver.parameters.log_search_progress = True


solution_printer = SolutionPrinter(limit=25)  # 30 is OK
t0 = time.time()
status = solver.Solve(model, solution_printer)
solver_final_status = solver.StatusName()
print(f"SOLVER STATUS: {solver_final_status}")
t1 = time.time()
print(solver.ResponseStats())
print(f"Elapsed time: {t1-t0:.2f} s")

if not solver_final_status == "INFEASIBLE":
    print(f"  => Solution found: {Messages.SUCCESS}")
    solution = export_solution(
        activity_data,
        model,
        solver,
        students_groups,
        week_structure=WEEK_STRUCTURE,
        start_day=ORIGIN_DATETIME,
    )
    xlsx_path = f"{output_dir}/schedule.xlsx"

    export_student_schedule_to_xlsx(
        xlsx_path,
        solution,
        students_groups,
        week_structure=WEEK_STRUCTURE,
        row_height=15,
        column_width=25,
    )
    # MODULES
    export_modules(
        solution=solution, output_dir=output_dir, filename="modules_activities.xlsx"
    )

    # MODULES PLANIFICATION
    export_modules(
        solution=solution,
        output_dir=output_dir,
        filename="modules_activities_planification.xlsx",
        sort_by=["kind", "start"],
    )

    # RESSOURCES
    export_ressources(solution=solution, output_dir=output_dir)

else:
    print(f"  => No solution found: {Messages.FAIL}")
