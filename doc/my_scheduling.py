import datetime
from ortools.sat.python import cp_model
import numpy as np
from collections import OrderedDict
import itertools
import pandas as pd
import os


def get_unique_rooms(activity_data):
    return np.sort(
        np.unique(np.concatenate([a["rooms"] for a in activity_data.values()]))
    )


def get_unique_students(activity_data):
    return np.sort(np.unique([a["students"] for a in activity_data.values()]))


def get_unique_teachers(activity_data):
    return np.sort(
        np.unique(np.concatenate([a["teachers"] for a in activity_data.values()]))
    )


class SolutionPrinter(cp_model.CpSolverSolutionCallback):
    """Print intermediate solutions."""

    def __init__(self):
        cp_model.CpSolverSolutionCallback.__init__(self)
        self.__solution_count = 0

    def on_solution_callback(self):
        """Called at each new solution."""
        print(
            "Solution %i, time = %f s, objective = %i"
            % (self.__solution_count, self.WallTime(), self.ObjectiveValue())
        )
        self.__solution_count += 1


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

module_data_dir = "modules_data/"
activity_data = {}
files = [f for f in os.listdir(module_data_dir) if f.endswith(".csv")]
for file in files:
    raw_data = pd.read_csv(
        module_data_dir + file, header=0, sep="\s*,\s*", engine="python"
    )
    raw_data = raw_data.T.to_dict()

    for k, v in raw_data.items():
        out = {}
        label = v["label"].strip()
        out["teachers"] = v["teachers"].split(";")
        out["rooms"] = [vv.strip() for vv in v["rooms"].split(";")]
        out["students"] = v["students"].strip()
        out["duration"] = int(v["duration"])
        out["kind"] = v["kind"].strip()
        after = v["after"].strip()
        if after == "None":
            after = None
        else:
            after = [vv.strip() for vv in after.split(";")]
        out["after"] = after
        out["min_offset"] = int(v["min_offset"])
        out["max_offset"] = int(v["max_offset"])
        activity_data[label] = out

teacher_data_dir = "teacher_data/"
teacher_data = []
files = [f for f in os.listdir(teacher_data_dir) if f.endswith(".csv")]
for file in files:
    raw_data = pd.read_csv(
        teacher_data_dir + file, header=0, sep="\s*,\s*", engine="python"
    )
    teacher_data.append(raw_data)
teacher_data = pd.concat(teacher_data)


# ROOM DATA
room_data = {
    "Room_A": {
        "unavailable": [
            (0, 3),
            (4, 50),
        ]
    }
}


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
unique_students = np.sort(
    np.unique(np.concatenate([v for k, v in students_groups.items()]))
).tolist()

unique_rooms = get_unique_rooms(activity_data).tolist()
# unique_students = get_unique_students(activity_data).tolist()
unique_teachers = get_unique_teachers(activity_data).tolist() + list(
    teacher_data.keys()
)
model = cp_model.CpModel()


# TEACHER UNAVAILABILITY
teacher_unavailable_intervals = OrderedDict(
    {teacher: [] for teacher in unique_teachers}
)

# def isocalendar_to_shift(start_date, year, week, day, shift):

"""
for teacher, tdata in teacher_data.items():
    if "unavailable" in tdata.keys():
        for start, end in tdata["unavailable"]:
            duration = end - start
            label = f"Unavailable_{teacher}_{start}_{end}"
            interval = model.NewIntervalVar(start, duration, end, label)
            teacher_unavailable_intervals[teacher].append(interval)"""
for _, tdata in teacher_data.T.to_dict().items():
    from_day = datetime.date.fromisocalendar(
        tdata["from_year"], tdata["from_week"], tdata["from_weekday"]
    )
    to_day = datetime.date.fromisocalendar(
        tdata["to_year"], tdata["to_week"], tdata["to_weekday"]
    )
    from_day_offset = max((from_day - START_DAY).days, 0)
    to_day_offset = max((to_day - START_DAY).days, 0)
    if from_day_offset < to_day_offset:
        from_shift = from_day_offset * TIME_SLOTS_PER_DAY + tdata["from_dayshift"]
        to_shift = to_day_offset * TIME_SLOTS_PER_DAY + tdata["to_dayshift"]
        duration = to_shift - from_shift
        interval = model.NewIntervalVar(
            from_shift, duration, to_shift, f"Unavailable_{label}_{0}"
        )
        teacher_unavailable_intervals["label"].append(interval)
# ROOM UNAVAILABILITY
room_unavailable_intervals = OrderedDict({room: [] for room in unique_rooms})
for room, rdata in room_data.items():
    if "unavailable" in rdata.keys():
        for start, end in rdata["unavailable"]:
            duration = end - start
            label = f"Unavailable_{room}_{start}_{end}"
            interval = model.NewIntervalVar(start, duration, end, label)
            room_unavailable_intervals[room].append(interval)


# STUDENT UNAVAILABILITY
student_unavailable_intervals = OrderedDict(
    {student: [] for student in unique_students}
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
            print(f"found shift {start}->{end}, day={start//10}")
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
        for student in unique_students:
            student_unavailable_intervals[student].append(interval)

"""
for week in range(MAX_WEEKS):
    for day in range(DAYS_PER_WEEK):
        if day < 5:
            night_interval = model.NewIntervalVar(
                day_shift + 7, 3, day_shift + 10, f"night_{day}"
            )
            lunch_interval = model.NewIntervalVar(
                day_shift + 3, 1, day_shift + 4, f"lunch_{day}"
            )
            for student in unique_students:
                student_unavailable_intervals[student].append(night_interval)
                student_unavailable_intervals[student].append(lunch_interval)
        elif day == 5:
            weekend_interval = model.NewIntervalVar(
                day_shift, 20, day_shift + 20, f"weekend_{day}"
            )
            for student in unique_students:
                student_unavailable_intervals[student].append(weekend_interval)
"""
activity_ends = []
data = OrderedDict()

previous_end = None
teacher_intervals = {t: [] for t in unique_teachers}
room_intervals = {r: [] for r in unique_rooms}
students_intervals = {s: [] for s in unique_students}

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
    after_list = act["after"]
    # CONSTRAINTS
    if after_list is not None:
        for after_label in after_list:
            previous_end = data[after_label]["end"]
            min_offset = act["min_offset"]
            model.Add(start >= previous_end + min_offset)
            max_offset = act["max_offset"]
            if max_offset >= 0:
                model.Add(start <= previous_end + max_offset)
    if act["kind"] in ["TD", "CM"]:
        start_m10 = model.NewIntVar(0, horizon, "start_mod_10")
        model.AddModuloEquality(start_m10, start, 10)
        model.Add(start_m10 != 3)

for teacher, intervals in teacher_intervals.items():
    if len(intervals) > 1:
        all_intervals = intervals + teacher_unavailable_intervals[teacher]
        model.AddNoOverlap(all_intervals)

for student, intervals in students_intervals.items():
    if len(intervals) > 1:
        all_intervals = intervals + student_unavailable_intervals[student]
        model.AddNoOverlap(all_intervals)

for room, intervals in room_intervals.items():
    if len(intervals) > 1:
        all_intervals = intervals + room_unavailable_intervals[room]
        model.AddNoOverlap(all_intervals)

# Makespan objective
makespan = model.NewIntVar(0, horizon, "makespan")
model.AddMaxEquality(makespan, activity_ends)
model.Minimize(makespan)

# Solve model.
solver = cp_model.CpSolver()
solution_printer = SolutionPrinter()
status = solver.Solve(model, solution_printer)

# PRINT SOLUTION
solution = {
    "label": [],
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
    "kind": [],
}


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
    solution["start"].append(start)
    solution["end"].append(end)
    solution["daystart"].append(start % TIME_SLOTS_PER_DAY)
    solution["dayend"].append(end % TIME_SLOTS_PER_DAY)
    solution["teacher"].append(teacher)
    solution["students"].append(students)
    solution["room"].append(room)

    solution["year"].append(date.year)
    solution["month"].append(date.month)
    solution["day"].append(date.day)
    solution["week"].append(isodate.week)
    solution["weekday"].append(weekday)
    solution["weekdayname"].append(DAYS_NAMES[isodate.weekday - 1])
    solution["kind"].append(activity_data[label]["kind"])


solution = pd.DataFrame(solution)
solution.sort_values("start", inplace=True)


xlout = None
for week, group in solution.groupby("week"):
    pass
