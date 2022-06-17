import datetime
from ortools.sat.python import cp_model
import numpy as np
import itertools
import pandas as pd
import os
from scipy import ndimage
import json

DAYS_NAMES = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
]


class Course:
    def __init__(self, label, color="red"):
        self.label = label
        self.color = color
        self.activities = {}

    def to_dict(self):
        out = {self.label: {"color": self.color}}
        actitivies_dict = {}
        for alabel, activity in self.activities.items():
            actitivies_dict[alabel] = activity.to_dict()
        out[self.label]["activities"] = actitivies_dict
        return out

    def add_activity(self, activity):
        activity.parent = self
        self.activities[activity.label] = activity


class Activity:
    def __init__(
        self,
        label,
        kind="TD",
        duration=1,
        teachers=None,
        rooms=None,
        students=None,
        after=None,
        parent=None,
    ):
        self.label = label
        self.kind = kind
        self.duration = duration
        self.teachers = []
        self.rooms = []
        self.students = students
        self.after = {}
        self.parent = parent
        if parent != None:
            parent.add_activity(self)

    def add_ressources(self, pool, kind="teachers", quantity=1):
        if kind == "teachers":
            self.teachers.append((quantity, pool))
        elif kind == "rooms":
            self.rooms.append((quantity, pool))

    def add_after(self, other, min_offset=0, max_offset=None):
        out = {}
        if min_offset is not None:
            out["min_offset"] = min_offset
        if max_offset is not None:
            out["max_offset"] = max_offset
        if len(out) > 0:
            if other.parent.label not in self.after.keys():
                self.after[other.parent.label] = {}
            self.after[other.parent.label][other.label] = out
        return self

    def add_after_manual(
        self, parent_label, activity_label, min_offset=0, max_offset=None
    ):
        out = {}
        if min_offset is not None:
            out["min_offset"] = min_offset
        if max_offset is not None:
            out["max_offset"] = max_offset
        if len(out) > 0:
            if parent_label not in self.after.keys():
                self.after[parent_label] = {}
            self.after[parent_label][activity_label] = out
        return self

    def reset_after(self):
        self.after = {}
        return self

    def to_dict(self):
        out = {
            "kind": self.kind,
            "duration": self.duration,
            "teachers": self.teachers,
            "rooms": self.rooms,
            "after": self.after,
            "students": self.students,
        }
        return out


def get_atomic_students_groups(students_groups):
    return np.sort(
        np.unique(np.concatenate([v for k, v in students_groups.items()]))
    ).tolist()


def get_unique_teachers_and_rooms(activity_data):
    rooms = []
    teachers = []
    for module, data in activity_data.items():
        if "activities" in data.keys():
            for label, activity in data["activities"].items():
                for _, rpool in activity["rooms"]:
                    rooms += rpool
                for _, tpool in activity["teachers"]:
                    teachers += tpool
    return np.sort(np.unique(teachers)), np.sort(np.unique(rooms))


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


def read_json_data(directory="", contains=None):
    all_data = {}
    for file in os.listdir(directory):
        if file.endswith(".json"):
            if contains != None:
                if contains in file:
                    use_file = True
                else:
                    use_file = False
            else:
                use_file = True
            if use_file:
                raw_data = json.load(open(directory + file))
                for label, data in raw_data.items():
                    all_data[label] = data
    return all_data


def create_unavailable_constraints(
    model,
    data={},
    prefix="Unavailable",
    start_day=datetime.date.fromisocalendar(2022, 1, 1),
    horizon=70,
):
    """
    Unavailable constraints.
    """
    intervals = {}
    for label, ldata_list in data.items():
        if "unavailable" in ldata_list.keys():
            for ldata in ldata_list["unavailable"]:
                if ldata["kind"] == "isocalendar":
                    from_year = ldata["from_year"]
                    from_week = ldata["from_week"]
                    from_weekday = ldata["from_weekday"]
                    from_dayslot = ldata["from_dayshift"]
                    to_year = ldata["to_year"]
                    to_week = ldata["to_week"]
                    to_weekday = ldata["to_weekday"]
                    to_dayslot = ldata["to_dayshift"]
                    from_slot = isocalendar_to_slot(
                        year=from_year,
                        week=from_week,
                        weekday=from_weekday,
                        dayslot=from_dayslot,
                        start_date=start_day,
                        slots_per_day=10,
                    )
                    to_slot = isocalendar_to_slot(
                        year=to_year,
                        week=to_week,
                        weekday=to_weekday,
                        dayslot=to_dayslot,
                        start_date=start_day,
                        slots_per_day=10,
                    )

                if "repeat" not in ldata.keys():
                    repeat = 1
                    repeat_pad = 70
                else:
                    repeat = ldata["repeat"]
                    repeat_pad = ldata["repeat_pad"]
                iteration = 0
                while iteration < repeat:
                    from_slot_repeat = max(from_slot, 0)
                    from_slot_repeat = min(from_slot_repeat, horizon)
                    to_slot_repeat = max(to_slot, 0)
                    to_slot_repeat = min(to_slot_repeat, horizon)
                    if from_slot_repeat < to_slot_repeat:
                        duration = to_slot - from_slot
                        interval_label = f"Unavailable_{label}_{from_slot_repeat}_{to_slot_repeat}_{repeat}"
                        interval = model.NewIntervalVar(
                            from_slot_repeat + iteration * repeat_pad,
                            duration,
                            to_slot_repeat + iteration * repeat_pad,
                            interval_label,
                        )
                        if label not in intervals.keys():
                            intervals[label] = []
                        intervals[label].append(interval)
                    iteration += 1

    return intervals


def isocalendar_to_slot(
    year=2022,
    week=1,
    weekday=1,
    dayslot=0,
    start_date=datetime.date.fromisocalendar(2022, 1, 1),
    slots_per_day=10,
):
    date = datetime.date.fromisocalendar(year, week, weekday)
    delta_days = (date - start_date).days
    return delta_days * slots_per_day + dayslot


def create_weekly_unavailable_intervals(model, week_structure, max_weeks):
    unavailable_intervals = []
    flat_week_structure = week_structure.flatten()
    flat_week_structure = np.append(
        flat_week_structure, flat_week_structure[:1]
    )  # LINK BETWEEN SUNDAY NIGHT AND MONDAY MORNING
    start = 0
    end = 0
    inside = False
    week_unavailable_intervals_start_end = []
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
                week_unavailable_intervals_start_end.append((start, end))
                inside = False
                start = 0
                end = 0
    TIME_SLOTS_PER_WEEK = week_structure.size
    for week in range(max_weeks):
        week_start_slot = TIME_SLOTS_PER_WEEK * week
        for iinter in range(len(week_unavailable_intervals_start_end)):
            start, end = week_unavailable_intervals_start_end[iinter]
            start += week_start_slot
            end += week_start_slot
            duration = end - start
            label = f"Week_forbidden_slot-{iinter}_on_week={week}"
            interval = model.NewIntervalVar(start, duration, end, label)
            unavailable_intervals.append(interval)
    return unavailable_intervals


def export_solution(
    activity_data, model, solver, students_groups, week_structure, start_day
):
    """
    Exports solution to Pandas Dataframe
    """
    solution = {
        "module": [],
        "label": [],
        "kind": [],
        "start": [],
        "end": [],
        "daystart": [],
        "dayend": [],
        "teachers": [],
        "students": [],
        "rooms": [],
        "year": [],
        "month": [],
        "day": [],
        "week": [],
        "weekday": [],
        "weekdayname": [],
    }
    time_slots_per_day = week_structure.shape[1]
    atomic_students_groups = get_atomic_students_groups(students_groups)
    for group in atomic_students_groups:
        solution[group] = []

    for mlabel, module in activity_data.items():
        for alabel, activity in module["activities"].items():
            activity_model = activity["model"]
            start = solver.Value(activity_model["start"])
            end = solver.Value(activity_model["end"])
            date = start_day + datetime.timedelta(days=int(start) // time_slots_per_day)
            isodate = date.isocalendar()
            weekday = isodate.weekday
            room = None
            teacher = None
            for alt_label, alt in activity_model["alts"].items():
                if solver.Value(alt["presence"]):
                    rooms = alt["rooms"]
                    teachers = alt["teachers"]
            students = activity["students"]
            solution["module"].append(mlabel)
            solution["label"].append(alabel)
            solution["kind"].append(activity["kind"])
            solution["start"].append(start)
            solution["end"].append(end)
            solution["daystart"].append(start % time_slots_per_day)
            solution["dayend"].append(end % time_slots_per_day)
            solution["teachers"].append(teachers)
            solution["students"].append(students)
            for group in atomic_students_groups:
                if group in students_groups[students]:
                    solution[group].append(1)
                else:
                    solution[group].append(0)
            solution["rooms"].append(rooms)

            solution["year"].append(date.year)
            solution["month"].append(date.month)
            solution["day"].append(date.day)
            solution["week"].append(isodate.week)
            solution["weekday"].append(weekday)
            solution["weekdayname"].append(DAYS_NAMES[isodate.weekday - 1])

    solution = pd.DataFrame(solution)
    solution.sort_values("start", inplace=True)
    return solution


def create_activities(
    activity_data,
    model,
    students_groups,
    horizon,
    teacher_unavailable_intervals,
    room_unavailable_intervals,
    weekly_unavailable_intervals,
):
    unique_teachers, unique_rooms = get_unique_teachers_and_rooms(activity_data)
    atomic_students_groups = get_atomic_students_groups(students_groups)
    teacher_intervals = {t: [] for t in unique_teachers}
    room_intervals = {r: [] for r in unique_rooms}
    students_intervals = {s: [] for s in atomic_students_groups}

    for file, module in activity_data.items():
        for label, activity in module["activities"].items():
            start = model.NewIntVar(0, horizon, "start_" + label)
            end = model.NewIntVar(0, horizon, "end_" + label)
            duration = activity["duration"]
            interval = model.NewIntervalVar(start, duration, end, "interval" + label)
            # after_list = activity["after"]
            model.Add(end == start + duration)
            teachers = activity["teachers"]
            rooms = activity["rooms"]
            students = activity["students"]
            sgroups = students_groups[students]
            act_data = {}
            act_data["start"] = start
            act_data["end"] = end
            act_data["interval"] = interval
            act_data["alts"] = {}
            act_presences = []
            # ALTERNATIVE EXISTENCE
            kind = []
            items = []
            for number, teacherpool in teachers:
                items.append(itertools.combinations(teacherpool, number))
                kind.append("teacher")
            for number, roompool in rooms:
                items.append(itertools.combinations(roompool, number))
                kind.append("room")
            combinations = [p for p in itertools.product(*items)]
            for icomb in range(len(combinations)):
                combination = combinations[icomb]
                comb_rooms = np.concatenate(
                    [
                        combination[i]
                        for i in range(len(combination))
                        if kind[i] == "room"
                    ]
                )
                comb_teachers = np.concatenate(
                    [
                        combination[i]
                        for i in range(len(combination))
                        if kind[i] == "teacher"
                    ]
                )
                alt_act_data = {}
                rooms_label = "_".join(comb_rooms)
                teachers_label = "_".join(comb_teachers)
                alt_label = f"{label}_{teachers_label}_{rooms_label}"
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
                for teacher in comb_teachers:
                    teacher_intervals[teacher].append(alt_interval)
                # ROOM INTERVALS
                for room in comb_rooms:
                    room_intervals[room].append(alt_interval)
                # STUDENTS INTERVALS
                for g in sgroups:
                    students_intervals[g].append(alt_interval)
                alt_act_data["start"] = alt_start
                alt_act_data["end"] = alt_end
                alt_act_data["presence"] = alt_presence
                alt_act_data["rooms"] = comb_rooms
                alt_act_data["teachers"] = comb_teachers
                act_data["alts"][alt_label] = alt_act_data
                act_presences.append(alt_presence)
            model.Add(sum(act_presences) == 1)
            activity["model"] = act_data

    for mlabel, module in activity_data.items():
        for alabel, activity in module["activities"].items():
            start = activity["model"]["start"]
            # CONSTRAINTS
            if "after" in activity.keys():
                after_dic = activity["after"]
                for after_mod, after_mod_dic in after_dic.items():
                    for after_label, after_data in after_mod_dic.items():
                        previous_end = activity_data[after_mod]["activities"][
                            after_label
                        ]["model"]["end"]
                        if "min_offset" in after_data.keys():
                            min_offset = after_data["min_offset"]
                            if min_offset >= 0:
                                model.Add(start >= previous_end + min_offset)
                        if "max_offset" in after_data.keys():
                            max_offset = after_data["max_offset"]
                            if max_offset >= 0:
                                model.Add(start <= previous_end + max_offset)
            if activity["kind"] in ["TD", "CM"]:
                start_m10 = model.NewIntVar(0, horizon, f"start_mod_10_{alabel}")
                model.AddModuloEquality(start_m10, start, 10)
                model.Add(start_m10 != 2)

            if "forbidden_weekdays" in activity.keys():
                forbidden_days = activity["forbidden_weekdays"]
                weeksstart = model.NewIntVar(0, horizon, f"weekstart_{alabel}")
                model.AddModuloEquality(weeksstart, start, 70)
                weekday = model.NewIntVar(0, horizon, f"weekday_{alabel}")
                model.AddDivisionEquality(weekday, weeksstart, 10)
                for fb in forbidden_days:
                    model.Add(weekday != fb - 1)

    for teacher, intervals in teacher_intervals.items():
        if len(intervals) > 1:
            if teacher in teacher_unavailable_intervals.keys():
                all_intervals = intervals + teacher_unavailable_intervals[teacher]
            else:
                all_intervals = intervals
            model.AddNoOverlap(all_intervals)

    for student, intervals in students_intervals.items():
        if len(intervals) > 1:
            all_intervals = intervals + weekly_unavailable_intervals
            model.AddNoOverlap(all_intervals)

    for room, intervals in room_intervals.items():
        if len(intervals) > 1:
            if room in room_unavailable_intervals:
                all_intervals = intervals + room_unavailable_intervals[room]
            else:
                all_intervals = intervals
            model.AddNoOverlap(all_intervals)


def export_student_schedule_to_xlsx(
    xlsx_path, solution, students_groups, week_structure, column_width=40, row_height=40
):
    days_per_week, time_slots_per_day = week_structure.shape
    atomic_students_groups = get_atomic_students_groups(students_groups)
    writer = pd.ExcelWriter(xlsx_path, engine="xlsxwriter")
    workbook = writer.book
    merge_format = workbook.add_format(
        {"align": "center", "valign": "vcenter", "border": 2}
    )
    N_unique_groups = len(atomic_students_groups)
    slots_df = pd.DataFrame({("Slot"): np.arange(time_slots_per_day)})
    day_df = {}
    for day in DAYS_NAMES:
        for group in atomic_students_groups:
            day_df[group] = np.zeros(time_slots_per_day) * np.nan
    day_df = pd.DataFrame(day_df)
    grid = np.zeros(
        (time_slots_per_day, days_per_week * len(atomic_students_groups)),
        dtype=np.int32,
    )
    row_offset = 2
    col_offset = 1
    for week, group in solution.groupby("week"):
        slots_df.to_excel(writer, sheet_name=f"Week_{week}", index=False, startrow=1)
        worksheet = writer.sheets[f"Week_{week}"]
        worksheet.set_default_row(row_height)
        worksheet.set_column(
            1, len(atomic_students_groups) * days_per_week + 1, column_width
        )  #
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
                group_index = atomic_students_groups.index(sub_group)
                grid[activity.daystart : activity.dayend, group_index] = 1
                gridl, nlabels = ndimage.label(grid)
                areas = ndimage.find_objects(gridl)
                for rslice, cslice in areas:
                    rstart = rslice.start + row_offset
                    cstart = cslice.start + day_offset
                    rstop = rslice.stop + row_offset - 1
                    cstop = cslice.stop + day_offset - 1
                    label = f"{activity.label}\n{activity.rooms}\n{activity.teachers}"
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
