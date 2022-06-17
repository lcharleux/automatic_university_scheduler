import datetime
from pickletools import StackObject
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
from scheduling import (
    read_json_data,
    get_unique_teachers_and_rooms,
    create_unavailable_constraints,
    create_weekly_unavailable_intervals,
    SolutionPrinter,
    export_solution,
    get_atomic_students_groups,
    DAYS_NAMES,
    create_activities,
    export_student_schedule_to_xlsx,
)


# SETUP
WEEK_STRUCTURE = np.array(
    [
        [1, 1, 1, 0, 1, 1, 1, 0, 0, 0],  # MONDAY
        [1, 1, 1, 0, 1, 1, 1, 0, 0, 0],  # TUESDAY
        [1, 1, 1, 0, 1, 1, 1, 0, 0, 0],  # WEDNESDAY
        [1, 1, 1, 0, 0, 0, 0, 0, 0, 0],  # THURSDAY
        [1, 1, 1, 0, 1, 1, 1, 0, 0, 0],  # FRIDAY
        [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],  # SATRUDAY
        [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],  # SUNDAY
    ]
)

DAYS_PER_WEEK, TIME_SLOTS_PER_DAY = WEEK_STRUCTURE.shape
MAX_WEEKS = 20
TIME_SLOTS_PER_WEEK = TIME_SLOTS_PER_DAY * DAYS_PER_WEEK
horizon = MAX_WEEKS * TIME_SLOTS_PER_WEEK
START_DAY = datetime.date.fromisocalendar(2022, 36, 1)
STOP_DAY = datetime.date.fromisocalendar(2022, 36, 1) + datetime.timedelta(
    weeks=MAX_WEEKS
)

# ACTIVITY GENERATION
"""# MATH500
class Course:
    pass
n_course = 14
label = "MATH500"
color = "green"
out = {label: {"color": color, "activities": {}}}
activity_label_template = "MATH5000_{group}_{index}"
teacher = "Math_Teacher_A"
group = "TDAB"
activity_template = {
    "kind": "TD",
    "duration": 1,
    "teachers": [[1, [teacher]]],
    "rooms": [[1, ["TD_Room_1", "TD_Room_2", "TD_Room_3", "TD_Room_4", "TD_Room_5"]]],
    "students": group,
    "after": {"MATH500": {after_activity_label: {"min_ofsset": 0}}},
}"""


print("Horizon = %i" % horizon)

activity_data_dir = "activity_data/"
teacher_data_dir = "teacher_data/"
room_data_dir = "room_data/"
teacher_data = read_json_data(teacher_data_dir)
activity_data = read_json_data(activity_data_dir)  # , contains="Meca501")
room_data = read_json_data(room_data_dir)


# STUDENTS GROUPS
students_groups = {
    "CM_TC": [
        "TPA1",
        "TPA2",
        "TPB1",
        "TPB2",
        "TPC1",
        "TPC2",
        "TPD1",
        "TPD2",
        "TPE1",
        "TPE2",
        "TPG1",
        "TPG2",
    ],
    "CM_MM": ["TPA1", "TPA2", "TPB1", "TPB2", "TPC1", "TPC2"],
    "CM_IAI": ["TPD1", "TPD2"],
    "CM_IDU": ["TPG1", "TPG2"],
    "TDAB": ["TPA1", "TPA2", "TPB1", "TPB2"],
    "TDA": ["TPA1", "TPA2"],
    "TDB": ["TPB1", "TPB2"],
    "TDC": ["TPC1", "TPC2"],
    "TDD": ["TPD1", "TPD2"],
    "TDE": ["TPE1", "TPE2"],
    "TDG": ["TPG1", "TPG2"],
    "TPA1": ["TPA1"],
    "TPA2": ["TPA2"],
    "TPB1": ["TPB1"],
    "TPB2": ["TPB2"],
    "TPC1": ["TPC1"],
    "TPC2": ["TPC2"],
    "TPD1": ["TPD1"],
    "TPD2": ["TPD2"],
    "TPE1": ["TPE1"],
    "TPE2": ["TPE2"],
    "TPG2": ["TPE2"],
    "TPG2": ["TPE2"],
    "TDA+B": ["TPA1", "TPA2", "TPB1", "TPB2"],
}


model = cp_model.CpModel()

# TEACHER UNAVAILABILITY
teacher_unavailable_intervals = create_unavailable_constraints(
    model, data=teacher_data, start_day=START_DAY, horizon=horizon
)
# ROOM UNAVAILABILITY
room_unavailable_intervals = create_unavailable_constraints(
    model, data=room_data, start_day=START_DAY, horizon=horizon
)

# NIGHT SHIFTS & LUNCH BREAKS AND WEEK-ENDS!
weekly_unavailable_intervals = create_weekly_unavailable_intervals(
    model, WEEK_STRUCTURE, MAX_WEEKS
)


create_activities(
    activity_data,
    model,
    students_groups,
    horizon=horizon,
    teacher_unavailable_intervals=teacher_unavailable_intervals,
    room_unavailable_intervals=room_unavailable_intervals,
    weekly_unavailable_intervals=weekly_unavailable_intervals,
)
# Makespan objective
activities_ends = []
for file, module in activity_data.items():
    for label, activity in module["activities"].items():
        activities_ends.append(activity["model"]["end"])

makespan = model.NewIntVar(0, horizon, "makespan")
model.AddMaxEquality(makespan, activities_ends)
model.Minimize(makespan)

# Solve model.
solver = cp_model.CpSolver()

solver.parameters.max_time_in_seconds = 60.0


solution_printer = SolutionPrinter(limit=100)
t0 = time.time()
status = solver.Solve(model, solution_printer)
t1 = time.time()
print(f"Elapsed time: {t1-t0:.2f} s")

solution = export_solution(
    activity_data,
    model,
    solver,
    students_groups,
    week_structure=WEEK_STRUCTURE,
    start_day=START_DAY,
)
xlsx_path = "outputs/schedule.xlsx"
if not os.path.isdir("./outputs"):
    os.mkdir("outputs")

export_student_schedule_to_xlsx(
    xlsx_path,
    solution,
    students_groups,
    week_structure=WEEK_STRUCTURE,
    row_height=30,
    column_width=30,
)
