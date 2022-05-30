from ortools.sat.python import cp_model
import numpy as np
from collections import OrderedDict
import itertools
import pandas as pd

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


# ACTIVITIES
"""activity_data = OrderedDict({
        "MATH_CM1": {
            "teachers": ["Teacher_A"],
            "rooms": ["Room_A"],
            "students": "CMA",
            "duration": 1,
            "after": ["MATH_Renforcement_2"],
            "offset": 5,
        },
        "MATH_CM2": {
            "teachers": ["Teacher_A"],
            "rooms": ["Room_A"],
            "students": "CMA",
            "duration": 1,
            "after": ["MATH_TD1_A", "MATH_TD1_B"],
            "offset": 5,
        },
        "MATH_TD1_A": {
            "teachers": ["Teacher_A"],
            "rooms": ["Room_A", "Room_B"],
            "students": "TDA",
            "duration": 1,
            "after": ["MATH_CM1"],
            "offset": 5,
        },
        "MATH_TD1_B": {
            "teachers": ["Teacher_A", "Teacher_B"],
            "rooms": ["Room_A", "Room_B"],
            "students": "TDB",
            "duration": 1,
            "after": ["MATH_CM1"],
            "offset": 5,
        },
        "MATH_TD2_A": {
            "teachers": ["Teacher_A", "Teacher_B"],
            "rooms": ["Room_B"],
            "students": "TDA",
            "duration": 1,
            "after": ["MATH_CM2"],
            "offset": 5,
        },
        "MATH_TD2_B": {
            "teachers": ["Teacher_A", "Teacher_B"],
            "rooms": ["Room_B"],
            "students": "TDB",
            "duration": 1,
            "after": ["MATH_CM2"],
            "offset": 5,
        },
        "MATH_TD3_A": {
            "teachers": ["Teacher_B"],
            "rooms": ["Room_B"],
            "students": "TDA",
            "duration": 1,
            "after": ["MATH_TD2_A"],
            "offset": 5,
        },
        "MATH_TD3_B": {
            "teachers": ["Teacher_B"],
            "rooms": ["Room_B"],
            "students": "TDB",
            "duration": 1,
            "after": ["MATH_TD2_B"],
            "offset": 5,
        },
        "MATH_Renforcement_1": {
            "teachers": ["Teacher_B"],
            "rooms": ["Room_B"],
            "students": "TDA+B",
            "duration": 1,
            "after": None,
            "offset": 5,
        },
        "MATH_Renforcement_2": {
            "teachers": ["Teacher_B"],
            "rooms": ["Room_B"],
            "students": "TDA+B",
            "duration": 1,
            "after": ["MATH_Renforcement_1"],
            "offset": 0,
        },
    }
)"""
raw_data = pd.read_csv("module_data.csv", header = 0, sep = "\s*,\s*", engine = "python")
raw_data = raw_data.T.to_dict()
activity_data = {}
for k, v in raw_data.items():
    out = {}
    label = v["label"].strip()
    out["teachers"] = v["teachers"].split(";")
    out["rooms"] = [vv.strip() for vv in v["rooms"].split(";")]
    out["students"] = v["students"].strip()
    out["duration"] = int(v["duration"])
    after = v["after"].strip()
    if after == "None":
        after = None
    else:
        after = [vv.strip() for vv in after.split(";")]  
    out["after"] = after
    out["offset"] = int(v["offset"])
    activity_data[label] = out


# TEACHER DATA
teacher_data = OrderedDict(
    {
        "Teacher_B": {
            "unavailable": [
                (2, 4),
                (8, 9),
            ]
        }
    }
)

# ROOM DATA
room_data = OrderedDict(
    {
        "Room_A": {
            "unavailable": [
                (0, 2),
                (8, 9),
            ]
        }
    }
)


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
unique_students = np.sort(np.unique(np.concatenate([v for k,v in students_groups.items()]))).tolist()

unique_rooms = get_unique_rooms(activity_data).tolist()
#unique_students = get_unique_students(activity_data).tolist()
unique_teachers = get_unique_teachers(activity_data).tolist() + list(
    teacher_data.keys()
)
model = cp_model.CpModel()

# TEACHER UNAVAILABILITY
teacher_unavailable_intervals = OrderedDict(
    {teacher: [] for teacher in unique_teachers}
)
for teacher, tdata in teacher_data.items():
    if "unavailable" in tdata.keys():
        for start, end in tdata["unavailable"]:
            duration = end - start
            label = f"Unavailable_{teacher}_{start}_{end}"
            interval = model.NewIntervalVar(start, duration, end, label)
            teacher_unavailable_intervals[teacher].append(interval)
# ROOM UNAVAILABILITY
room_unavailable_intervals = OrderedDict(
    {room: [] for room in unique_rooms}
)
for room, rdata in room_data.items():
    if "unavailable" in rdata.keys():
        for start, end in rdata["unavailable"]:
            duration = end - start
            label = f"Unavailable_{room}_{start}_{end}"
            interval = model.NewIntervalVar(start, duration, end, label)
            room_unavailable_intervals[room].append(interval)



horizon = 50
for label, act in activity_data.items():
    horizon += act["duration"]
print("Horizon = %i" % horizon)

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
            offset = act["offset"]
            model.Add(start >= previous_end + offset)

for teacher, intervals in teacher_intervals.items():
    if len(intervals) > 1:
        all_intervals = intervals + teacher_unavailable_intervals[teacher]
        model.AddNoOverlap(all_intervals)

for student, intervals in students_intervals.items():
    if len(intervals) > 1:
        model.AddNoOverlap(intervals)

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
solution = {"label":[], "start":[], "end":[], "teacher":[], "students":[], "room":[]}

for label, activity in data.items():
    start = solver.Value(activity["start"])
    end = solver.Value(activity["end"])
    room = None
    teacher = None
    for alt_label, alt in activity["alts"].items():
        if solver.Value(alt["presence"]):
            room = alt["room"]
            teacher = alt["teacher"]
    #print(label, start, end, room, teacher)
    students = activity_data[label]["students"]
    solution["label"].append(label)
    solution["start"].append(start)
    solution["end"].append(end)
    solution["teacher"].append(teacher)
    solution["students"].append(students)
    solution["room"].append(room)


solution = pd.DataFrame(solution)  
