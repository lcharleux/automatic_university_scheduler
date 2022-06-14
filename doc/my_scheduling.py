import datetime
from ortools.sat.python import cp_model
import numpy as np
from collections import OrderedDict
import itertools
import pandas as pd
import os
from scipy import ndimage
import json


def get_unique_rooms(activity_data):
    return np.sort(
        np.unique(np.concatenate([a["rooms"] for a in activity_data.values()]))
    )


def get_unique_students_groups(activity_data):
    return np.sort(np.unique([a["students"] for a in activity_data.values()]))


def get_unique_teachers(activity_data):
    return np.sort(
        np.unique(np.concatenate([a["teachers"] for a in activity_data.values()]))
    )


class SolutionPrinter(cp_model.CpSolverSolutionCallback):
    """Print intermediate solutions."""

    def __init__(self, limit=3):
        cp_model.CpSolverSolutionCallback.__init__(self)
        self.__solution_count = 0
        self.__solution_limit = limit

    def on_solution_callback(self):
        """Called at each new solution."""
        print(
            "Solution %i, time = %f s, objective = %i"
            % (self.__solution_count, self.WallTime(), self.ObjectiveValue())
        )
        self.__solution_count += 1
        if self.__solution_count >= self.__solution_limit:
            print("Stop search after %i solutions" % self.__solution_limit)
            self.StopSearch()

    def solution_count(self):
        return self.__solution_count


def read_json_data(directory=""):
    all_data = {}
    for file in os.listdir(directory):
        if file.endswith(".json"):
            data = json.load(open(directory + file))
            for k, v in data.items():
                if k not in all_data.keys():
                    all_data[k] = v
                else:
                    print(f"Warning, data {k} defined more than once.")
    return all_data


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
DAYS_NAMES = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
]
DAYS_PER_WEEK, TIME_SLOTS_PER_DAY = WEEK_STRUCTURE.shape
MAX_WEEKS = 20
TIME_SLOTS_PER_WEEK = TIME_SLOTS_PER_DAY * DAYS_PER_WEEK
horizon = MAX_WEEKS * TIME_SLOTS_PER_WEEK
START_DAY = datetime.date.fromisocalendar(2022, 36, 1)
print("Horizon = %i" % horizon)

activity_data_dir = "activity_data/"
teacher_data_dir = "teacher_data/"
room_data_dir = "room_data/"
teacher_data = read_json_data(teacher_data_dir)
activity_data = read_json_data(activity_data_dir)
room_data = read_json_data(room_data_dir)


# STUDENTS GROUPS
students_groups = {
    "CMA": ["TPA1", "TPA2", "TPB1", "TPB2"],
    "TDA": ["TPA1", "TPA2"],
    "TDB": ["TPB1", "TPB2"],
    "TDC": ["TPC1", "TPC2"],
    "TPA1": ["TPA1"],
    "TPA2": ["TPA2"],
    "TPB1": ["TPB1"],
    "TPB2": ["TPB2"],
    "TPC1": ["TPC1"],
    "TPC2": ["TPC2"],
    "TDA+B": ["TPA1", "TPA2", "TPB1", "TPB2"],
}
unique_students_groups = np.sort(
    np.unique(np.concatenate([v for k, v in students_groups.items()]))
).tolist()

unique_rooms = get_unique_rooms(activity_data).tolist()
# unique_students_groups = get_unique_students_groups(activity_data).tolist()
unique_teachers = get_unique_teachers(activity_data).tolist() + list(
    teacher_data.keys()
)
model = cp_model.CpModel()

# TEACHER UNAVAILABILITY
def create_unavailable_constraints(model, data={}, prefix="Unavailable"):
    intervals = {}
    for label, ldata_list in data.items():
        if "unavailable" in ldata_list.keys():
            for ldata in ldata_list["unavailable"]:
                if ldata["kind"] == "isocalendar":
                    from_day = datetime.date.fromisocalendar(
                        ldata["from_year"], ldata["from_week"], ldata["from_weekday"]
                    )
                    to_day = datetime.date.fromisocalendar(
                        ldata["to_year"], ldata["to_week"], ldata["to_weekday"]
                    )
                    from_day_offset = (from_day - START_DAY).days
                    to_day_offset = (to_day - START_DAY).days
                    from_day_offset = max(from_day_offset, 0)
                    to_day_offset = max(to_day_offset, 0)
                    # from_day_offset = min(from_day_offset, horizon)
                    # to_day_offset = min(to_day_offset, horizon)
                    if from_day_offset < to_day_offset:
                        from_shift = (
                            from_day_offset * TIME_SLOTS_PER_DAY
                            + ldata["from_dayshift"]
                        )
                        to_shift = (
                            to_day_offset * TIME_SLOTS_PER_DAY + ldata["to_dayshift"]
                        )
                        duration = to_shift - from_shift

                if "repeat" not in ldata.keys():
                    repeat = 1
                    repeat_pad = 70
                else:
                    repeat = ldata["repeat"]
                    repeat_pad = ldata["repeat_pad"]
                iteration = 0
                while iteration < repeat:
                    interval_label = (
                        f"Unavailable_{label}_{from_shift}_{to_shift}_{repeat}"
                    )
                    interval = model.NewIntervalVar(
                        from_shift + iteration * repeat_pad,
                        duration,
                        to_shift + iteration * repeat_pad,
                        interval_label,
                    )
                    if label not in intervals.keys():
                        intervals[label] = []
                    intervals[label].append(interval)
                    iteration += 1
    return intervals


teacher_unavailable_intervals = create_unavailable_constraints(model, data=teacher_data)
room_unavailable_intervals = create_unavailable_constraints(model, data=room_data)
# ROOM UNAVAILABILITY
"""room_unavailable_intervals = {}
for room, rdata in room_data.items():
    if "unavailable" in rdata.keys():
        for start, end in rdata["unavailable"]:
            duration = end - start
            label = f"Unavailable_{room}_{start}_{end}"
            interval = model.NewIntervalVar(start, duration, end, label)
            if room not in room_unavailable_intervals.keys():
                room_unavailable_intervals[room] = []
            room_unavailable_intervals[room].append(interval)

"""
# STUDENT UNAVAILABILITY
student_unavailable_intervals = OrderedDict(
    {student: [] for student in unique_students_groups}
)

# NIGHT SHIFTS & LUNCH BREAKS AND WEEK-ENDS!
flat_week_structure = WEEK_STRUCTURE.flatten()
flat_week_structure = np.append(
    flat_week_structure, flat_week_structure[:1]
)  # LINK BETWEEN SUNDAY NIGHT AND MONDAY MORNING
start = 0
end = 0
inside = False
week_forbidden_intervals = []
for islot in range(len(flat_week_structure)):
    # day_shift = TIME_SLOTS_PER_WEEK * week + TIME_SLOTS_PER_DAY * day
    slot = flat_week_structure[islot]
    # print(f"islot={islot}, slot={slot}")
    if slot == 0:
        if inside:
            end = islot
            # print(f"End = {end}")
        else:
            start = islot
            inside = True
            # print(f"Start = {start}")
    else:
        if inside:
            end = islot
            # print(f"found shift {start}->{end}, day={start//10}")
            week_forbidden_intervals.append((start, end))
            inside = False
            start = 0
            end = 0

for week in range(MAX_WEEKS):
    week_start_slot = TIME_SLOTS_PER_WEEK * week
    for iinter in range(len(week_forbidden_intervals)):
        start, end = week_forbidden_intervals[iinter]
        start += week_start_slot
        end += week_start_slot
        duration = end - start
        label = f"Week_forbidden_slot-{iinter}_on_week={week}"
        interval = model.NewIntervalVar(start, duration, end, label)
        for student in unique_students_groups:
            student_unavailable_intervals[student].append(interval)

activity_ends = []
data = OrderedDict()

previous_end = None
teacher_intervals = {t: [] for t in unique_teachers}
room_intervals = {r: [] for r in unique_rooms}
students_intervals = {s: [] for s in unique_students_groups}

for label, act in activity_data.items():
    start = model.NewIntVar(0, horizon, "start_" + label)
    end = model.NewIntVar(0, horizon, "end_" + label)
    duration = act["duration"]
    after_list = act["after"]
    model.Add(end == start + duration)
    teachers = act["teachers"]
    rooms = act["rooms"]
    students = act["students"]
    sgroups = students_groups[students]
    act_data = OrderedDict()
    act_data["start"] = start
    act_data["end"] = end
    act_data["alts"] = OrderedDict()
    act_presences = []

    for teacher, room in itertools.product(teachers, rooms):
        alt_act_data = OrderedDict()
        alt_label = f"{label}_{teacher}_{room}"
        alt_presence = model.NewBoolVar("presence_" + alt_label)
        alt_start = model.NewIntVar(0, horizon, "start_" + alt_label)
        alt_end = model.NewIntVar(0, horizon, "end_" + alt_label)
        alt_interval = model.NewOptionalIntervalVar(
            alt_start, duration, alt_end, alt_presence, "interval" + alt_label
        )
        # ALTERNATIVE CONSTRAINTS
        model.Add(start == alt_start).OnlyEnforceIf(alt_presence)
        model.Add(end == alt_end).OnlyEnforceIf(alt_presence)

        # TEACHER INTERVALS
        teacher_intervals[teacher].append(alt_interval)
        # ROOM INTERVALS
        room_intervals[room].append(alt_interval)
        # STUDENTS INTERVALS
        for g in sgroups:
            students_intervals[g].append(alt_interval)
        alt_act_data["start"] = alt_start
        alt_act_data["end"] = alt_end
        alt_act_data["presence"] = alt_presence
        alt_act_data["room"] = room
        alt_act_data["teacher"] = teacher
        act_data["alts"][alt_label] = alt_act_data
        act_presences.append(alt_presence)
    previous_end = end
    activity_ends.append(previous_end)
    model.Add(sum(act_presences) == 1)
    # starts[label] =
    data[label] = act_data

for label, act in activity_data.items():
    start = data[label]["start"]

    # CONSTRAINTS
    if "after" in act.keys():
        after_dic = act["after"]
        for after_label, after_data in after_dic.items():
            previous_end = data[after_label]["end"]
            min_offset = after_data["min_offset"]
            if min_offset >= 0:
                model.Add(start >= previous_end + min_offset)
            max_offset = after_data["max_offset"]
            if max_offset >= 0:
                model.Add(start <= previous_end + max_offset)
    if act["kind"] in ["TD", "CM"]:
        start_m10 = model.NewIntVar(0, horizon, "start_mod_10")
        model.AddModuloEquality(start_m10, start, 10)
        model.Add(start_m10 != 2)

for teacher, intervals in teacher_intervals.items():
    if len(intervals) > 1:
        if teacher in teacher_unavailable_intervals.keys():
            all_intervals = intervals + teacher_unavailable_intervals[teacher]
        else:
            all_intervals = intervals
        model.AddNoOverlap(all_intervals)

for student, intervals in students_intervals.items():
    if len(intervals) > 1:
        all_intervals = intervals + student_unavailable_intervals[student]
        model.AddNoOverlap(all_intervals)

for room, intervals in room_intervals.items():
    if len(intervals) > 1:
        if room in room_unavailable_intervals:
            all_intervals = intervals + room_unavailable_intervals[room]
        else:
            all_intervals = intervals
        model.AddNoOverlap(all_intervals)
# Makespan objective
makespan = model.NewIntVar(0, horizon, "makespan")
model.AddMaxEquality(makespan, activity_ends)
model.Minimize(makespan)

# Solve model.
solver = cp_model.CpSolver()
solver.parameters.max_time_in_seconds = 10.0

solution_printer = SolutionPrinter(limit=5)
status = solver.Solve(model, solution_printer)

# PRINT SOLUTION
solution = {
    "label": [],
    "kind": [],
    "start": [],
    "end": [],
    "daystart": [],
    "dayend": [],
    "teacher": [],
    "students": [],
    "room": [],
    "year": [],
    "month": [],
    "day": [],
    "week": [],
    "weekday": [],
    "weekdayname": [],
}
for group in unique_students_groups:
    solution[group] = []


for label, activity in data.items():
    start = solver.Value(activity["start"])
    end = solver.Value(activity["end"])
    date = START_DAY + datetime.timedelta(days=int(start) // TIME_SLOTS_PER_DAY)
    isodate = date.isocalendar()
    weekday = isodate.weekday
    room = None
    teacher = None
    for alt_label, alt in activity["alts"].items():
        if solver.Value(alt["presence"]):
            room = alt["room"]
            teacher = alt["teacher"]
    students = activity_data[label]["students"]
    solution["label"].append(label)
    solution["kind"].append(activity_data[label]["kind"])
    solution["start"].append(start)
    solution["end"].append(end)
    solution["daystart"].append(start % TIME_SLOTS_PER_DAY)
    solution["dayend"].append(end % TIME_SLOTS_PER_DAY)
    solution["teacher"].append(teacher)
    solution["students"].append(students)
    for group in unique_students_groups:
        if group in students_groups[students]:
            solution[group].append(1)
        else:
            solution[group].append(0)
    solution["room"].append(room)

    solution["year"].append(date.year)
    solution["month"].append(date.month)
    solution["day"].append(date.day)
    solution["week"].append(isodate.week)
    solution["weekday"].append(weekday)
    solution["weekdayname"].append(DAYS_NAMES[isodate.weekday - 1])


solution = pd.DataFrame(solution)
solution.sort_values("start", inplace=True)


writer = pd.ExcelWriter("schedule.xlsx", engine="xlsxwriter")
workbook = writer.book
merge_format = workbook.add_format(
    {"align": "center", "valign": "vcenter", "border": 2}
)
N_unique_groups = len(unique_students_groups)
slots_df = pd.DataFrame({("Slot"): np.arange(TIME_SLOTS_PER_DAY)})
day_df = {}
for day in DAYS_NAMES:
    for group in unique_students_groups:
        day_df[group] = np.zeros(TIME_SLOTS_PER_DAY) * np.nan
day_df = pd.DataFrame(day_df)
grid = np.zeros(
    (TIME_SLOTS_PER_DAY, DAYS_PER_WEEK * len(unique_students_groups)), dtype=np.int32
)
row_offset = 2
col_offset = 1
for week, group in solution.groupby("week"):
    slots_df.to_excel(writer, sheet_name=f"Week_{week}", index=False, startrow=1)
    worksheet = writer.sheets[f"Week_{week}"]
    for nday in range(len(DAYS_NAMES)):
        day_name = DAYS_NAMES[nday]
        day_df.to_excel(
            writer,
            sheet_name=f"Week_{week}",
            index=False,
            startrow=1,
            startcol=col_offset + nday * N_unique_groups,
        )
        date = datetime.date.fromisocalendar(
            group.year.values[0], group.week.values[0], nday + 1
        )
        worksheet.merge_range(
            0,
            col_offset + nday * N_unique_groups,
            0,
            col_offset + (nday + 1) * (N_unique_groups) - 1,
            f"{day_name} {date}",
            merge_format,
        )

    # week_activities = group.label.unique()
    for label, activity in group.iterrows():
        grid *= 0
        students = activity.students
        sub_groups = students_groups[students]
        day_offset = N_unique_groups * (activity.weekday - 1) + col_offset
        for sub_group in sub_groups:
            group_index = unique_students_groups.index(sub_group)
            grid[activity.daystart : activity.dayend, group_index] = 1
            gridl, nlabels = ndimage.label(grid)
            areas = ndimage.find_objects(gridl)
            for rslice, cslice in areas:
                rstart = rslice.start + row_offset
                cstart = cslice.start + day_offset
                rstop = rslice.stop + row_offset - 1
                cstop = cslice.stop + day_offset - 1
                label = f"{activity.label}\n{activity.room}\n{activity.teacher}"
                if (rstart != rstop) or (cstart != cstop):
                    worksheet.merge_range(
                        rstart,
                        cstart,
                        rstop,
                        cstop,
                        label,
                        merge_format,
                    )
                else:
                    worksheet.write(rstart, cstart, label, merge_format)


writer.save()
