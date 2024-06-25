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
# 1. ROOMS & TEACHERS
# tracked_ressources = {
#     "teachers": get_unique_ressources_in_activities(activity_data, kind="teachers"),
#     "rooms": get_unique_ressources_in_activities(activity_data, kind="rooms"),
# }
# existing_data = pd.read_csv("existing_activities/extraction_data.csv").fillna("")
tracked_ressources = read_from_yaml(f"{preprocessing_dir}/tracked_ressources.yaml")
ressource_existing_intervals = {
    k: {t: [] for t in tracked_ressources[k]} for k in ["teachers", "rooms"]
}
# dump_to_yaml(
#     {k: v.tolist() for k, v in tracked_ressources.items()},
#     f"{output_dir}/tracked_ressources.yaml",
# )

# 2. STUDENTS
# school = "POLYTECH Annecy"
# unique_students = list(students_groups.keys())
# students_existing_intervals = {k: [] for k in students_groups.keys()}


# for index, row in existing_data.iterrows():
#     year = row.year
#     week = row.week
#     weekday = row.weekday
#     from_dayslot = row.from_dayslot
#     to_dayslot = row.to_dayslot
#     act = {
#         "kind": "isocalendar",
#         "from_year": year,
#         "from_week": week,
#         "from_weekday": weekday,
#         "from_dayslot": from_dayslot,
#         "to_year": year,
#         "to_week": week,
#         "to_weekday": weekday,
#         "to_dayslot": to_dayslot,
#     }
#     for ressource_kind in ["teachers", "rooms"]:
#         tracked_ress = tracked_ressources[ressource_kind]
#         ressources = row[ressource_kind]
#         if ressources == "":
#             ressources = []
#         else:
#             ressources = [t.strip() for t in ressources.split(",")]
#         for ressource in ressources:
#             if ressource in tracked_ress:
#                 ressource_existing_intervals[ressource_kind][ressource].append(act)

#     if row.school == school:
#         for students in [s.strip() for s in row.students.split(",")]:
#             if students in students_existing_intervals.keys():
#                 students_existing_intervals[students].append(act)

# 3. MERGE THE FUCK

# teacher_reverse_dict = {v["full_name"]: k for k, v in teacher_data.items()}
teacher_data_fullnames = {v["full_name"]: v for k, v in teacher_data.items()}

# for teacher, acts in ressource_existing_intervals["teachers"].items():
#     if teacher not in teacher_data_fullnames.keys():
#         teacher_data_fullnames[teacher] = {"full_name": teacher, "unavailable": []}
#     teacher_data_fullnames[teacher]["unavailable"] += acts
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

    if True:
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
            # else:
            #     print(f"Group {group} has no existing constraints.")
            # new_d[k] = {"unavailable": []}
            # for act in v["unavailable"]:
            #     new_d[k]["unavailable"].append(act)
        # calendar_data += new_d
        students_existing_intervals = calendar_data
    else:
        students_existing_intervals = [calendar_data, calendar_data]  # THIS IS DIRTY

    # for students, acts in ressource_existing_intervals["students"].items():
    #     if students not in students_existing_intervals[-1].keys():
    #         students_data[-1][students] = {"unavailable": []}
    #     students_existing_intervals[-1][students]["unavailable"] += acts
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


def write_student_unavailability_matrices():
    origin_monday = ORIGIN_MONDAY
    week_structure = (WEEK_STRUCTURE == 0) * 1
    matrix0 = np.concatenate([week_structure for _ in range(MAX_WEEKS)]).flatten()

    matrices = {k: matrix0.copy() for k in students_atomic_groups}
    # for i in range(len(students_data)):
    for group, intervals in students_existing_intervals.items():
        for interval in intervals["unavailable"]:
            if interval["kind"] == "isocalendar":
                from_week = interval["from_week"]
                to_week = interval["to_week"]
                from_weekday = interval["from_weekday"]
                to_weekday = interval["to_weekday"]
                start = (
                    TIME_SLOTS_PER_WEEK * (from_week - 1)
                    + TIME_SLOTS_PER_DAY * (from_weekday - 1)
                    + interval["from_dayslot"]
                )
                end = (
                    TIME_SLOTS_PER_WEEK * (to_week - 1)
                    + TIME_SLOTS_PER_DAY * (to_weekday - 1)
                    + interval["to_dayslot"]
                )
            elif interval["kind"] == "datetime":
                start_datetime = DateTime.from_str(interval["start"])
                end_datetime = DateTime.from_str(interval["end"])
                start = math.floor(
                    (start_datetime - origin_monday).to_slots(
                        slot_duration=TIME_SLOT_DURATION
                    )
                )
                end = math.ceil(
                    (end_datetime - origin_monday).to_slots(
                        slot_duration=TIME_SLOT_DURATION
                    )
                )
            for student in students_groups[group]:
                matrices[student][start:end] += 1

    for agroup, matrix in matrices.items():
        d = 1
        w = origin_monday.isocalendar().week
        y = origin_monday.isocalendar().year
        datetime = DateTime.fromisocalendar(y, w, 1)
        with open(
            f"{output_dir}/students_unavailability_matrix_{agroup}.txt",
            "w",
            encoding="utf-8",
        ) as f:
            for r in matrix.reshape(-1, TIME_SLOTS_PER_DAY):
                f.write(
                    f"{y}-W{str(w).zfill(2)}-d{d} "
                    + "".join([str(rr) for rr in r])
                    + "\n"
                )
                d += 1
                if d == DAYS_PER_WEEK + 1:
                    datetime += TimeDelta.from_str("1w")
                    w = datetime.isocalendar().week
                    y = datetime.isocalendar().year
                    d = 1
    return matrices


students_matrices = write_student_unavailability_matrices()
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
    writer = pd.ExcelWriter(
        f"{output_dir}/modules_activities.xlsx", engine="xlsxwriter"
    )
    unique_modules = solution.module.unique()
    unique_modules.sort()
    for module in unique_modules:
        module_solution = solution[solution.module == module].sort_values(["start"])
        module_solution = module_solution[
            [
                "label",
                "week",
                "weekday",
                "weekdayname",
                "starttime",
                "endtime",
                "kind",
                "students",
                "teachers",
                "rooms",
                "year",
                "month",
                "day",
                "daystart",
                "dayend",
            ]
        ]
        sheet_name = f"{module}"
        module_solution.to_excel(writer, sheet_name=sheet_name, index=False, startrow=1)
        worksheet = writer.sheets[sheet_name]
        workbook = writer.book
        my_format = workbook.add_format(
            {"align": "center", "valign": "vcenter", "border": 0, "font_size": 11}
        )
        worksheet.set_column("A:A", 50, my_format)
        worksheet.set_column("B:G", 12, my_format)
        worksheet.set_column("H:H", 20, my_format)
        worksheet.set_column("I:J", 70, my_format)
        worksheet.set_column("K:N", 12, my_format)
        nrows = module_solution.shape[0] + 2
        tag = f"A2:N{nrows}"
        worksheet.autofilter(tag)

    writer.close()

    # MODULES PLANIFICATION
    writer = pd.ExcelWriter(
        f"{output_dir}/modules_activities_planification.xlsx", engine="xlsxwriter"
    )
    unique_modules = solution.module.unique()
    unique_modules.sort()

    for module in unique_modules:
        module_solution = solution[solution.module == module].sort_values(
            ["kind", "start"]
        )
        module_solution = module_solution[
            [
                "label",
                "week",
                "weekday",
                "weekdayname",
                "starttime",
                "endtime",
                "kind",
                "students",
                "teachers",
                "rooms",
                "year",
                "month",
                "day",
                "daystart",
                "dayend",
            ]
        ]
        sheet_name = f"{module}"
        module_solution.to_excel(writer, sheet_name=sheet_name, index=False, startrow=1)
        worksheet = writer.sheets[sheet_name]
        workbook = writer.book
        my_format = workbook.add_format(
            {"align": "center", "valign": "vcenter", "border": 0, "font_size": 11}
        )
        worksheet.set_column("A:A", 50, my_format)
        worksheet.set_column("B:G", 12, my_format)
        worksheet.set_column("H:H", 20, my_format)
        worksheet.set_column("I:J", 30, my_format)
        worksheet.set_column("K:N", 12, my_format)

    writer.close()

    # RESSOURCES
    for ressources in ["teachers", "rooms"]:
        writer = pd.ExcelWriter(
            f"{output_dir}/{ressources}_activities.xlsx", engine="xlsxwriter"
        )
        unique_ressources = np.unique(np.concatenate(solution[ressources].values))
        unique_ressources.sort()

        for ressource in unique_ressources:
            loc = solution[ressources].apply(lambda a: np.isin(ressource, a))
            ressource_solution = solution[loc].sort_values(["start"])
            ressource_solution = ressource_solution[
                [
                    "module",
                    "label",
                    "week",
                    "weekday",
                    "weekdayname",
                    "starttime",
                    "endtime",
                    "kind",
                    "students",
                    "teachers",
                    "rooms",
                    "year",
                    "month",
                    "day",
                    "daystart",
                    "dayend",
                ]
            ]
            sheet_name = f"{ressource}"
            ressource_solution.to_excel(
                writer, sheet_name=sheet_name, index=False, startrow=1
            )
            worksheet = writer.sheets[sheet_name]
            workbook = writer.book
            my_format = workbook.add_format(
                {"align": "center", "valign": "vcenter", "border": 0, "font_size": 11}
            )
            worksheet.set_column("A:A", 20, my_format)
            worksheet.set_column("B:B", 50, my_format)
            worksheet.set_column("C:H", 12, my_format)
            worksheet.set_column("I:I", 20, my_format)
            worksheet.set_column("J:K", 70, my_format)
            worksheet.set_column("L:N", 12, my_format)
            nrows = ressource_solution.shape[0] + 2
            tag = f"A2:P{nrows}"
            worksheet.autofilter(tag)

        writer.close()
else:
    print(f"  => No solution found: {Messages.FAIL}")
