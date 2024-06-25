import datetime
from ortools.sat.python import cp_model
import numpy as np
import itertools
import pandas as pd
import os
from scipy import ndimage
import json
from automatic_university_scheduler.datetime import (
    DateTime,
    TimeDelta,
    TimeInterval,
    read_time_intervals,
    datetime_to_slot,
)
import yaml

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
    """
    A class used to represent a Course.

    ...

    Attributes
    ----------
    label : str
        a string representing the label of the course
    color : str
        a string representing the color of the course, default is "red"
    activities : dict
        a dictionary storing the activities of the course, keys are activity labels and values are Activity objects

    Methods
    -------
    to_dict():
        Returns a dictionary representation of the Course object.
    add_activity(activity):
        Adds an activity to the course's activities dictionary and sets the course as the parent of the activity.
    """

    def __init__(self, label, color="red"):
        self.label = label
        self.color = color
        self.activities = {}

    def to_dict(self):
        """
        Returns a dictionary representation of the Course object.

        Returns
        -------
        dict
            a dictionary with course label as key and another dictionary as value which contains color and activities of the course
        """
        out = {self.label: {"color": self.color}}
        actitivies_dict = {}
        for alabel, activity in self.activities.items():
            actitivies_dict[alabel] = activity.to_dict()
        out[self.label]["activities"] = actitivies_dict
        return out

    def add_activity(self, activity):
        """
        Adds an activity to the course's activities dictionary and sets the course as the parent of the activity.

        Parameters
        ----------
        activity : Activity
            an Activity object to be added to the course
        """
        activity.parent = self
        self.activities[activity.label] = activity


class Activity:
    """
    A class used to represent an Activity.

    ...

    Attributes
    ----------
    label : str
        a string representing the label of the activity
    kind : str
        a string representing the kind of the activity, default is "TD"
    duration : int
        an integer representing the duration of the activity, default is 1
    teachers : list
        a list storing the teachers of the activity
    rooms : list
        a list storing the rooms of the activity
    students : list
        a list storing the students of the activity
    after : dict
        a dictionary storing the activities that should be after this activity
    parent : Course
        a Course object representing the parent course of the activity
    min_start_slot : int
        an integer representing the minimum start slot of the activity
    max_start_slot : int
        an integer representing the maximum start slot of the activity

    Methods
    -------
    add_ressources(pool, kind="teachers", quantity=1):
        Adds resources to the activity.
    add_after(other, min_offset=0, max_offset=None):
        Adds an activity that should be after this activity.
    add_multiple_after(others, *args, **kwargs):
        Adds multiple activities that should be after this activity.
    add_after_manual(parent_label, activity_label, min_offset=0, max_offset=None):
        Manually adds an activity that should be after this activity.
    reset_after():
        Resets the 'after' attribute of the activity.
    to_dict():
        Returns a dictionary representation of the Activity object.
    """

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
        min_start_slot=None,
        max_start_slot=None,
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
        self.min_start_slot = min_start_slot
        self.max_start_slot = max_start_slot

    def add_ressources(self, pool, kind="teachers", quantity=1):
        """
        Adds resources to the activity.

        Parameters:
        pool : list
            a list of resources to be added to the activity
        kind : str, optional
            a string representing the kind of the resources, either "teachers" or "rooms", default is "teachers"
        quantity : int, optional
            an integer representing the quantity of the resources to be added, default is 1

        Returns:
        None
        """
        if kind == "teachers":
            self.teachers.append((quantity, pool))
        elif kind == "rooms":
            self.rooms.append((quantity, pool))

    def add_after(self, other, min_offset=0, max_offset=None):
        """
        Adds resources to the activity.

        Parameters:
        pool : list
            a list of resources to be added to the activity
        kind : str, optional
            a string representing the kind of the resources, either "teachers" or "rooms", default is "teachers"
        quantity : int, optional
            an integer representing the quantity of the resources to be added, default is 1

        Returns:
        None
        """
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

    def add_multiple_after(self, others, *args, **kwargs):
        for other in others:
            self.add_after(other, *args, **kwargs)
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
            "min_start_slot": self.min_start_slot,
            "max_start_slot": self.max_start_slot,
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
            print("Stopped search after %i solutions" % self.__solution_limit)
            self.StopSearch()

    def solution_count(self):
        return self.__solution_count


def read_json_data(directory="", contains=None):
    all_data = {}
    if not directory.endswith("/"):
        directory += "/"
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
    model, start_day, data={}, prefix="Unavailable", horizon=10000, slots_per_day=96
):
    """
    Unavailable constraints.
    """
    intervals = {}
    for label, ldata_list in data.items():
        if "unavailable" in ldata_list.keys():
            for ldata in ldata_list["unavailable"]:
                if ldata["kind"] == "isocalendar":
                    print(
                        f"Warning: using legacy unavailable on {label} constraints definition."
                    )
                    from_year = ldata["from_year"]
                    from_week = ldata["from_week"]
                    from_weekday = ldata["from_weekday"]
                    from_dayslot = ldata["from_dayslot"]
                    to_year = ldata["to_year"]
                    to_week = ldata["to_week"]
                    to_weekday = ldata["to_weekday"]
                    to_dayslot = ldata["to_dayslot"]
                    from_slot = isocalendar_to_slot(
                        year=from_year,
                        week=from_week,
                        weekday=from_weekday,
                        dayslot=from_dayslot,
                        start_date=start_day,
                        slots_per_day=slots_per_day,
                    )
                    to_slot = isocalendar_to_slot(
                        year=to_year,
                        week=to_week,
                        weekday=to_weekday,
                        dayslot=to_dayslot,
                        start_date=start_day,
                        slots_per_day=slots_per_day,
                    )

                    if "repeat" not in ldata.keys():
                        repeat = 1
                    else:
                        repeat = ldata["repeat"]
                    if "repeat_pad" not in ldata.keys():
                        repeat_pad = slots_per_day * 7
                    else:
                        repeat_pad = ldata["repeat_pad"]
                    iteration = 0
                    while iteration < repeat:
                        from_slot_repeat = max(from_slot, 0)
                        from_slot_repeat = min(from_slot_repeat, horizon)
                        to_slot_repeat = max(to_slot, 0)
                        to_slot_repeat = min(to_slot_repeat, horizon)
                        if from_slot_repeat < to_slot_repeat:
                            # duration = to_slot - from_slot
                            interval_label = f"{prefix}_{label}_{from_slot_repeat}_{to_slot_repeat}_{repeat}"
                            start = from_slot_repeat + iteration * repeat_pad
                            end = to_slot_repeat + iteration * repeat_pad
                            start = min(start, horizon)
                            end = min(end, horizon)
                            duration = end - start
                            if start < end:
                                interval = model.NewIntervalVar(
                                    start,
                                    duration,
                                    end,
                                    interval_label,
                                )
                                if label not in intervals.keys():
                                    intervals[label] = []
                                intervals[label].append(interval)
                        iteration += 1
                elif ldata["kind"] == "datetime":
                    if "description" not in ldata.keys():
                        description = ""
                    else:
                        description = ldata["description"]
                    origin_datetime = start_day
                    slot_duration = TimeDelta(days=1) / slots_per_day
                    horizon_datetime = origin_datetime + horizon * slot_duration
                    ldata2 = {
                        k: v
                        for k, v in ldata.items()
                        if k not in ["kind", "description"]
                    }
                    # ldata2["origin_datetime"] = start_day
                    time_intervals = read_time_intervals(**ldata2)
                    slots_intervals = []
                    for ti in time_intervals:
                        slots = ti.to_slots(
                            origin_datetime, horizon_datetime, slot_duration
                        )
                        if slots != None:
                            slots_intervals.append(slots)

                    for slot_id, slots in enumerate(slots_intervals):
                        start = slots[0]
                        end = slots[1]
                        duration = end - start
                        interval_label = (
                            f"{prefix}_{description}_{label}_{start}_{end}_R{slot_id}"
                        )
                        interval = model.NewIntervalVar(
                            start,
                            duration,
                            end,
                            interval_label,
                        )
                        if label not in intervals.keys():
                            intervals[label] = []
                        intervals[label].append(interval)

    return intervals


def isocalendar_to_slot(
    year=2022,
    week=1,
    weekday=1,
    dayslot=0,
    start_date=DateTime.fromisocalendar(2022, 1, 1),
    slots_per_day=96,
):
    date = DateTime.fromisocalendar(year, week, weekday)
    delta_days = (date - start_date).days
    return delta_days * slots_per_day + dayslot


def create_weekly_unavailable_intervals(model, week_structure, max_weeks):
    unavailable_intervals = []
    flat_week_structure = week_structure.flatten()
    flat_week_structure = np.append(
        flat_week_structure, [1]
    )  # LINK BETWEEN SUNDAY NIGHT AND MONDAY MORNING
    start = 0
    end = 0
    inside = False
    week_unavailable_intervals_start_end = []
    for islot in range(len(flat_week_structure)):
        # day_slot = TIME_SLOTS_PER_WEEK * week + TIME_SLOTS_PER_DAY * day
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
                # print(f"found slot {start}->{end}, day={start//10}")
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
        "color": [],
        "duration": [],
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
        "starttime": [],
        "endtime": [],
    }
    time_slots_per_day = week_structure.shape[1]
    atomic_students_groups = get_atomic_students_groups(students_groups)
    for group in atomic_students_groups:
        solution[group] = []

    for mlabel, module in activity_data.items():
        if "color" in module.keys():
            mcolor = module["color"]
        else:
            mcolor = None
        for alabel, activity in module["activities"].items():
            activity_model = activity["model"]
            start = solver.Value(activity_model["start"])
            end = solver.Value(activity_model["end"])
            duration = end - start
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
            solution["color"].append(mcolor)
            solution["module"].append(mlabel)
            solution["label"].append(alabel)
            solution["kind"].append(activity["kind"])
            solution["start"].append(start)
            solution["end"].append(end)
            solution["duration"].append(duration)
            daystart = start % time_slots_per_day
            solution["daystart"].append(daystart)
            dayend = end % time_slots_per_day
            solution["dayend"].append(dayend)
            solution["starttime"].append(day_slot_to_time(daystart))
            solution["endtime"].append(day_slot_to_time(dayend))
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
    students_unavailable_intervals,
    weekly_unavailable_intervals,
    activities_kinds,
    origin_datetime,
    slot_duration,
):
    unique_teachers, unique_rooms = get_unique_teachers_and_rooms(activity_data)
    atomic_students_groups = get_atomic_students_groups(students_groups)
    teacher_intervals = {t: [] for t in unique_teachers}
    room_intervals = {r: [] for r in unique_rooms}
    students_intervals = {s: [] for s in atomic_students_groups}
    students_lunch_intervals = {s: [] for s in atomic_students_groups}
    atomic_students_unavailable_intervals = {}

    # for students_unavailable_subintervals in students_unavailable_intervals:
    #     atomic_students_unavailable_intervals.append({})
    #     for group, intervals in students_unavailable_subintervals.items():
    #         agroups = students_groups[group]
    #         for agroup in agroups:
    #             if agroup not in atomic_students_unavailable_intervals[-1].keys():
    #                 atomic_students_unavailable_intervals[-1][agroup] = []
    #             atomic_students_unavailable_intervals[-1][agroup] += intervals
    for group, intervals in students_unavailable_intervals.items():
        atomic_groups = students_groups[group]
        for atomic_group in atomic_groups:
            if atomic_group not in atomic_students_unavailable_intervals.keys():
                atomic_students_unavailable_intervals[atomic_group] = []
            atomic_students_unavailable_intervals[atomic_group] += intervals

    for file, module in activity_data.items():
        for label, activity in module["activities"].items():
            start = model.NewIntVar(0, horizon, "start_" + label)
            end = model.NewIntVar(0, horizon, "end_" + label)
            duration = activity["duration"]
            interval = model.NewIntervalVar(start, duration, end, "interval" + label)
            model.Add(end == start + duration)
            teachers = activity["teachers"]
            rooms = activity["rooms"]
            students = activity["students"]
            if students == None:
                sgroups = []
            else:
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
                    if activity["kind"] == "lunch":
                        students_lunch_intervals[g].append(alt_interval)
                    else:
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
            if "min_start_slot" in activity.keys():
                if activity["min_start_slot"] != None:
                    model.Add(start >= activity["min_start_slot"])
            if "max_start_slot" in activity.keys():
                if activity["max_start_slot"] != None:
                    model.Add(start <= activity["max_start_slot"])
            if "earliest_datetime" in activity.keys():
                earliest_datetime = DateTime(activity["earliest_datetime"])
                earliest_slot = datetime_to_slot(
                    earliest_datetime, origin_datetime, slot_duration, round="ceil"
                )
                model.Add(start >= earliest_slot)
            if "latest_datetime" in activity.keys():
                latest_datetime = DateTime(activity["latest_datetime"])
                latest_slot = datetime_to_slot(
                    latest_datetime, origin_datetime, slot_duration, round="floor"
                )
                model.Add(start <= latest_slot)

            # ALLOWED START SLOTS PER ACTIVITY KIND

            activity_allowed_slots = activities_kinds[activity["kind"]][
                "allowed_start_time_slots"
            ]
            start_m96 = model.NewIntVar(0, horizon, f"start_mod_96_{alabel}")
            model.AddModuloEquality(start_m96, start, 96)
            all_slots = np.arange(96)
            activity_forbidden_slots = list(
                set(all_slots) - set(activity_allowed_slots)
            )
            for forbidden_slot in activity_forbidden_slots:
                model.Add(start_m96 != forbidden_slot)

            if "forbidden_weekdays" in activity.keys():
                forbidden_days = activity["forbidden_weekdays"]
                weeksstart = model.NewIntVar(0, horizon, f"weekstart_{alabel}")
                model.AddModuloEquality(weeksstart, start, 672)
                weekday = model.NewIntVar(0, horizon, f"weekday_{alabel}")
                model.AddDivisionEquality(weekday, weeksstart, 96)
                for fb in forbidden_days:
                    model.Add(weekday != fb - 1)

    # THIS MUST BE WRONG
    # for teacher_unavailable_subintervals in teacher_unavailable_intervals:
    #     for teacher, intervals in teacher_intervals.items():
    #         if len(intervals) > 1:
    #             print(teacher_unavailable_subintervals)
    #             if teacher in teacher_unavailable_subintervals.keys():
    #                 all_intervals = (
    #                     intervals + teacher_unavailable_subintervals[teacher]
    #                 )
    #             else:
    #                 all_intervals = intervals
    #             model.AddNoOverlap(all_intervals)

    for teacher, intervals in teacher_intervals.items():
        if len(intervals) > 0:
            model.AddNoOverlap(intervals)
            # print("HEREEEEE", teacher_unavailable_intervals)
            if teacher in teacher_unavailable_intervals.keys():
                for interval in intervals:
                    for unavaible_interval in teacher_unavailable_intervals[teacher]:
                        model.AddNoOverlap([unavaible_interval, interval])

    for student, intervals in students_intervals.items():
        if len(intervals) > 1:
            model.AddNoOverlap(intervals)
            for interval in intervals:
                for weekly_unavailable_interval in weekly_unavailable_intervals:
                    model.AddNoOverlap([interval, weekly_unavailable_interval])
                for student_lunch_interval in students_lunch_intervals[student]:
                    model.AddNoOverlap([interval, student_lunch_interval])
                # print(students_unavailable_intervals.keys())
                for (
                    atomic_student_unavailable_interval
                ) in atomic_students_unavailable_intervals[student]:
                    model.AddNoOverlap([interval, atomic_student_unavailable_interval])
            # all_intervals = intervals + weekly_unavailable_intervals
            # model.AddNoOverlap(all_intervals)

    # for (
    #     atomic_students_unavailable_subintervals
    # ) in atomic_students_unavailable_intervals:
    #     for student, intervals in students_intervals.items():
    #         if (len(intervals) > 1) and (
    #             student in atomic_students_unavailable_subintervals.keys()
    #         ):
    #             for interval in intervals:
    #                 for atomic_students_unavailable_subinterval in atomic_students_unavailable_subintervals[student]:
    #                     model.AddNoOverlap([atomic_students_unavailable_subinterval, interval])

    # all_intervals = (
    #     intervals + atomic_students_unavailable_subintervals[student]
    # )
    # model.AddNoOverlap(all_intervals)

    # for student, intervals in students_intervals.items():
    #     if len(intervals) > 1:
    #         all_intervals = intervals + students_lunch_intervals[student]
    #         model.AddNoOverlap(all_intervals)

    for room, intervals in room_intervals.items():
        if len(intervals) > 1:
            if room in room_unavailable_intervals:
                all_intervals = intervals + room_unavailable_intervals[room]
            else:
                all_intervals = intervals
            model.AddNoOverlap(all_intervals)
    return (
        atomic_students_unavailable_intervals,
        teacher_unavailable_intervals,
        room_unavailable_intervals,
        students_unavailable_intervals,
        weekly_unavailable_intervals,
    )


def export_student_schedule_to_xlsx(
    xlsx_path, solution, students_groups, week_structure, column_width=40, row_height=80
):
    days_per_week, time_slots_per_day = week_structure.shape
    atomic_students_groups = get_atomic_students_groups(students_groups)
    writer = pd.ExcelWriter(xlsx_path, engine="xlsxwriter")
    workbook = writer.book
    merge_format = workbook.add_format(
        {"align": "center", "valign": "vcenter", "border": 2, "font_size": 15}
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
        # worksheet.set_row(0, slots_df.shape[1], merge_format)
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
            cell_format = workbook.add_format(
                {
                    "align": "center",
                    "valign": "vcenter",
                    "border": 2,
                    "bg_color": activity["color"],
                    "color": "white",
                    "font_size": 15,
                }
            )
            grid *= 0
            students = activity.students
            sub_groups = students_groups[students]
            day_offset = N_unique_groups * (activity.weekday - 1) + col_offset
            for sub_group in sub_groups:
                group_index = atomic_students_groups.index(sub_group)
                grid[activity.daystart : activity.dayend, group_index] = 1
            gridl, nlabels = ndimage.label(grid)
            # print(gridl)
            # print(sub_group)
            areas = ndimage.find_objects(gridl)
            for rslice, cslice in areas:
                rstart = rslice.start + row_offset
                cstart = cslice.start + day_offset
                rstop = rslice.stop + row_offset - 1
                cstop = cslice.stop + day_offset - 1
                label = f"{activity.label}\n{activity.rooms}\n{activity.teachers}"
                label_flat = label.replace("\n", "-")
                # print("activity")
                # print(f"{label_flat}: R={rstart}-{rstop}; C={cstart}-{cstop}")
                if (rstart != rstop) or (cstart != cstop):
                    worksheet.merge_range(
                        rstart,
                        cstart,
                        rstop,
                        cstop,
                        label,
                        cell_format,
                    )
                else:
                    worksheet.write(rstart, cstart, label, cell_format)

    writer.close()


def day_slot_to_time(slot):
    hour = str(slot // 4).zfill(2)
    minutes = str((slot % 4) * 15).zfill(2)
    return f"{hour}:{minutes}"


def get_semester_duration(model, activity_data, students_groups, horizon):
    """
    Returns the duration of the semester.
    """
    activities_ends = []
    for file, module in activity_data.items():
        for label, activity in module["activities"].items():
            if activity["kind"] != "lunch":
                activities_ends.append(activity["model"]["end"])
    makespan = model.NewIntVar(0, horizon, "makespan")
    model.AddMaxEquality(makespan, activities_ends)
    return makespan


def get_absolute_week_duration_deviation(
    model,
    activity_data,
    students_groups,
    students_atomic_groups,
    horizon,
    max_weeks,
    slots_per_week=672,
):
    """
    Returns the absolute deviation from the mean week duration of each atomic student group.
    """
    week_duration = {
        group: [[] for i in range(max_weeks)] for group in students_atomic_groups
    }
    total_activities_duration = {group: 0 for group in students_atomic_groups}
    for file, module in activity_data.items():
        for label, activity in module["activities"].items():
            start = activity["model"]["start"]
            end = activity["model"]["end"]
            duration = activity["duration"]
            for group in students_groups[activity["students"]]:
                total_activities_duration[group] += duration
            week = model.NewIntVar(0, max_weeks, "makespan")
            model.AddDivisionEquality(week, start, 672)
            for i in range(max_weeks):
                is_week = model.NewBoolVar("is_week")
                model.Add(week == i).OnlyEnforceIf(is_week)
                model.Add(week != i).OnlyEnforceIf(is_week.Not())
                duration_on_week = model.NewIntVar(
                    0, slots_per_week, "duration_on_week"
                )
                model.Add(duration_on_week == duration).OnlyEnforceIf(is_week)
                model.Add(duration_on_week == 0).OnlyEnforceIf(is_week.Not())
                for group in students_groups[activity["students"]]:
                    week_duration[group][i].append(duration_on_week)
    # Remove empty groups:
    week_duration_curated = {}
    for group, wd in week_duration.items():
        l = sum([len(d) for d in wd])
        if l != 0:
            week_duration_curated[group] = wd

    week_duration_sums = []
    week_duration_residuals = []
    for group, wd in week_duration_curated.items():
        total_duration_per_group = 0
        for nw, w in enumerate(wd):
            if len(w) != 0:
                week_duration_sums.append(sum(w))
                total_duration_per_group += sum(w)
            else:
                week_duration_sums.append(0)
        mean_week_duration = model.NewIntVar(
            0, slots_per_week, f"mean_week_duration_{group}"
        )
        model.AddDivisionEquality(
            mean_week_duration, total_activities_duration[group], len(wd)
        )
        for w in wd:
            week_duration = sum(w)
            abs_week_residual = model.NewIntVar(0, slots_per_week, "mean_week_duration")
            positive_residual = model.NewBoolVar("mean_week_duration")
            model.Add(week_duration - mean_week_duration >= 0).OnlyEnforceIf(
                positive_residual
            )
            model.Add(week_duration - mean_week_duration < 0).OnlyEnforceIf(
                positive_residual.Not()
            )
            model.Add(
                abs_week_residual == week_duration - mean_week_duration
            ).OnlyEnforceIf(positive_residual)
            model.Add(
                abs_week_residual == mean_week_duration - week_duration
            ).OnlyEnforceIf(positive_residual.Not())
            week_duration_residuals.append(abs_week_residual)
    makespan = model.NewIntVar(0, horizon, "makespan")
    model.Add(makespan == sum(week_duration_residuals))
    return makespan


def load_setup(path):
    """
    Load the setup file.
    """
    with open(path) as f:
        data = yaml.safe_load(f)
    origin_datetime = DateTime.from_str(data["ORIGIN_DATETIME"])
    horizon_datetime = DateTime.from_str(data["HORIZON_DATETIME"])
    origin_monday = DateTime.fromisocalendar(
        origin_datetime.isocalendar().year, origin_datetime.isocalendar().week, 1
    )
    horizon_monday = DateTime.fromisocalendar(
        horizon_datetime.isocalendar().year, horizon_datetime.isocalendar().week, 1
    )
    out = {}
    out["WEEK_STRUCTURE"] = WEEK_STRUCTURE = read_week_structure(data["WEEK_STRUCTURE"])
    ONE_WEEK = TimeDelta.from_str("1w")
    ONE_DAY = TimeDelta.from_str("1d")
    out["WEEK_STRUCTURE"] = read_week_structure(data["WEEK_STRUCTURE"])
    out["DAYS_PER_WEEK"], out["TIME_SLOTS_PER_DAY"] = out["WEEK_STRUCTURE"].shape
    out["ORIGIN_DATETIME"] = origin_datetime
    out["HORIZON_DATETIME"] = horizon_datetime
    out["HORIZON_MONDAY"] = horizon_monday
    out["ORIGIN_MONDAY"] = origin_monday
    out["MAX_WEEKS"] = (horizon_monday - origin_monday) // ONE_WEEK + 1
    out["TIME_SLOT_DURATION"] = ONE_DAY / out["TIME_SLOTS_PER_DAY"]
    out["TIME_SLOTS_PER_WEEK"] = out["DAYS_PER_WEEK"] * out["TIME_SLOTS_PER_DAY"]
    out["HORIZON"] = out["MAX_WEEKS"] * out["TIME_SLOTS_PER_WEEK"]
    out["ACTIVITIES_KINDS"] = data["ACTIVITIES_KINDS"]
    return out


def read_week_structure(data):
    """
    Reads the week structure from a list of strings, typically obtained from a YAML file.
    Each string in the list represents a day and should contain a sequence of '0' and '1' characters
    representing unavailable and available time slots, respectively. Spaces in the strings are ignored.

    Parameters:
    data (List[str]): The week structure data. Each string in the list represents a day and should contain
                      a sequence of '0' and '1' characters representing unavailable and available time slots,
                      respectively.

    Returns:
    np.array: A 2D numpy array of integers representing the week structure. Each row corresponds to a day
              and each column corresponds to a time slot. A '1' indicates that the corresponding time slot
              on the corresponding day is available, and a '0' indicates that it is not.
    """
    WEEK_STRUCTURE = np.array([list(day.replace(" ", "")) for day in data]).astype(int)
    return WEEK_STRUCTURE
