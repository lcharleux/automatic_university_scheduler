from ortools.sat.python import cp_model
from automatic_university_scheduler.database import StaticActivity
import itertools
import numpy as np
from scipy import ndimage
from sqlalchemy.orm import Session
from sqlalchemy import create_engine, select
from automatic_university_scheduler.database import Project, Base
from automatic_university_scheduler.utils import create_directory
import pandas as pd
import os


def absolute_week_duration_deviation(
    project, model, activities_starts, activities_durations
):
    """ """
    setup = project.setup
    max_weeks = setup["MAX_WEEKS"]
    time_slots_per_week = setup["TIME_SLOTS_PER_WEEK"]
    horizon = setup["HORIZON"]
    origin_monday = project.setup["ORIGIN_MONDAY"]
    origin_monday_slot = project.datetime_to_slot(origin_monday)
    students_groups_ids = [g.id for g in project.atomic_students]
    students_week_duration_dic = {
        gid: [[] for i in range(max_weeks)] for gid in students_groups_ids
    }
    activities_students_dic = {}
    for activity in project.activities:
        aid = activity.id
        activities_students_dic[aid] = [s.id for s in activity.students.students]
    total_activities_duration_per_group = {gid: 0 for gid in students_groups_ids}
    for aid, start in activities_starts.items():
        activity_week_number = model.NewIntVar(0, max_weeks, f"activity_{aid}_week")
        model.AddDivisionEquality(
            activity_week_number, start - origin_monday_slot, time_slots_per_week
        )
        activity_duration = activities_durations[aid]
        for student in activity.students.students:
            gid = student.id
            total_activities_duration_per_group[gid] += activity_duration
        for week_id in range(max_weeks):
            activity_is_on_week = model.NewBoolVar(f"is_week_{week_id}_{aid}")
            model.Add(activity_week_number == week_id).OnlyEnforceIf(
                activity_is_on_week
            )
            model.Add(activity_week_number != week_id).OnlyEnforceIf(
                activity_is_on_week.Not()
            )
            activity_duration_on_week = model.NewIntVar(
                0, time_slots_per_week, "duration_on_week"
            )
            model.Add(activity_duration_on_week == activity_duration).OnlyEnforceIf(
                activity_is_on_week
            )
            model.Add(activity_duration_on_week == 0).OnlyEnforceIf(
                activity_is_on_week.Not()
            )
            for student in activity.students.students:
                gid = student.id
                students_week_duration_dic[gid][week_id].append(
                    activity_duration_on_week
                )
    # REMOVE EMPTY GROUPS
    students_week_duration_dic_curated = {}
    for group, wd in students_week_duration_dic.items():
        curated_duration = sum([len(d) for d in wd])
        if curated_duration != 0:
            students_week_duration_dic_curated[group] = wd

    week_duration_residuals = []
    for group, group_week_durations in students_week_duration_dic_curated.items():
        mean_week_duration_per_group = int(
            round(total_activities_duration_per_group[group] / max_weeks)
        )
        for w in group_week_durations:
            week_duration = sum(w)
            abs_week_residual = model.NewIntVar(
                0, time_slots_per_week, "mean_week_duration"
            )
            positive_residual = model.NewBoolVar("mean_week_duration")
            model.Add(week_duration - mean_week_duration_per_group >= 0).OnlyEnforceIf(
                positive_residual
            )
            model.Add(week_duration - mean_week_duration_per_group < 0).OnlyEnforceIf(
                positive_residual.Not()
            )
            model.Add(
                abs_week_residual == week_duration - mean_week_duration_per_group
            ).OnlyEnforceIf(positive_residual)
            model.Add(
                abs_week_residual == mean_week_duration_per_group - week_duration
            ).OnlyEnforceIf(positive_residual.Not())
            week_duration_residuals.append(abs_week_residual)
    cost_value = model.NewIntVar(0, horizon, "makespan")
    model.Add(cost_value == sum(week_duration_residuals))
    return cost_value


class SolutionPrinter(cp_model.CpSolverSolutionCallback):
    """Print intermediate solutions."""

    def __init__(self, engine, activities_starts, activities_alternative_ressources, dump_dir,  limit=3):
        cp_model.CpSolverSolutionCallback.__init__(self)
        self.__solution_count = 0
        self.__solution_limit = limit
        self.engine = engine
        self.activities_starts = activities_starts
        self.activities_alternative_ressources = activities_alternative_ressources
        self.dump_dir = dump_dir

    def on_solution_callback(self):
        """Called at each new solution."""
        print(
            "Solution %i, time = %f s, objective = %i"
            % (self.__solution_count, self.WallTime(), self.ObjectiveValue())
        )
        export_solution_to_database(self, self.engine, self.activities_starts, self.activities_alternative_ressources)
        dump_solution(self.dump_dir, self.engine)
        self.__solution_count += 1
        if self.__solution_count >= self.__solution_limit:
            print("Stopped search after %i solutions" % self.__solution_limit)
            self.StopSearch()

    def solution_count(self):
        return self.__solution_count


def delete_imported_static_activities(session):
    existing_static_activities = (
        session.query(StaticActivity).where(StaticActivity.kind == "imported").all()
    )
    for static_activity in existing_static_activities:
        session.delete(static_activity)
    session.commit()


def create_activities_variables(model, project):
    activities_intervals = {}
    activities_starts = {}
    activities_ends = {}
    activities_durations = {}
    activities_alternative_ressources = {}
    s_factor = project.succession_constraint_relaxation_factor
    atomic_students = project.atomic_students
    rooms = project.rooms
    teachers = project.teachers
    rooms_dic = {r.id: r for r in rooms}
    teachers_dic = {t.id: t for t in teachers}
    atomic_students_intervals = {s.id: [] for s in atomic_students}
    room_intervals = {r.id: [] for r in rooms}
    teacher_intervals = {t.id: [] for t in teachers}
    activities = project.activities
    starts_after_constraints = project.starts_after_constraints
    horizon = project.horizon

    for activity in activities:
        aid = activity.id
        said = str(aid).zfill(4)
        start = model.NewIntVar(0, horizon, f"start_{said}")
        end = model.NewIntVar(0, horizon, f"end_{said}")
        if activity.start is not None:
            model.AddHint(start, activity.start)
        if activity.earliest_start_slot is not None:
            model.Add(start >= activity.earliest_start_slot)
        if activity.latest_start_slot is not None:
            model.Add(start <= activity.latest_start_slot)
        duration = activity.duration
        # model.Add(end == start + duration) # overkill ? Enforced by IntervalVar : https://developers.google.com/optimization/reference/python/sat/python/cp_model#newintervalvar
        interval = model.NewIntervalVar(start, duration, end, f"activity_{said}")
        atomic_students_ids = [i.id for i in activity.students.students]
        for sid in atomic_students_ids:
            atomic_students_intervals[sid].append(interval)
        activities_intervals[aid] = interval
        activities_starts[aid] = start
        activities_ends[aid] = end
        activities_durations[aid] = duration
        activities_alternative_ressources[aid] = {"rooms": [], "teachers": []}
        # ALTERNATIVES
        items = []
        kind = []
        alt_presences = []
        pre_allocated_rooms = activity.allocated_rooms
        pre_allocated_rooms_ids_set = set([r.id for r in pre_allocated_rooms])
        has_pre_allocated_rooms = len(pre_allocated_rooms) > 0
        pre_allocated_teachers = activity.allocated_teachers
        pre_allocated_teachers_ids_set = set([t.id for t in pre_allocated_teachers])
        has_pre_allocated_teachers = len(pre_allocated_teachers) > 0
        room_pool = activity.room_pool
        room_pool_ids = [r.id for r in room_pool]
        room_count = activity.room_count
        items.append(itertools.combinations(room_pool_ids, room_count))
        kind.append("room")
        teacher_pool = activity.teacher_pool
        teacher_pool_ids = [t.id for t in teacher_pool]
        teacher_count = activity.teacher_count
        items.append(itertools.combinations(teacher_pool_ids, teacher_count))
        kind.append("teacher")
        combinations = [p for p in itertools.product(*items)]
        for icomb, combination in enumerate(combinations):
            comb_rooms = np.concatenate(
                [combination[i] for i in range(len(combination)) if kind[i] == "room"]
            )

            comb_teachers = np.concatenate(
                [
                    combination[i]
                    for i in range(len(combination))
                    if kind[i] == "teacher"
                ]
            )
            alt_presence = model.NewBoolVar(f"presence_{said}_alt{icomb}")
            if has_pre_allocated_rooms and has_pre_allocated_teachers:
                if (
                    set(comb_rooms) == pre_allocated_rooms_ids_set
                    and set(comb_teachers) == pre_allocated_teachers_ids_set
                ):
                    model.AddHint(alt_presence, 1)
                else:
                    model.AddHint(alt_presence, 0)

            alt_start = model.NewIntVar(0, horizon, f"start_{said}_alt{icomb}")
            alt_end = model.NewIntVar(0, horizon, f"end_{said}_alt{icomb}")
            model.Add(alt_end == alt_start + duration)
            alt_interval = model.NewOptionalIntervalVar(
                alt_start,
                duration,
                alt_end,
                alt_presence,
                f"activity_{said}_alt{icomb}",
            )
            model.Add(start == alt_start).OnlyEnforceIf(alt_presence)
            alt_presences.append(alt_presence)
            for tid in comb_teachers:
                teacher_intervals[tid].append(alt_interval)
            for rid in comb_rooms:
                room_intervals[rid].append(alt_interval)
            activities_alternative_ressources[aid]["rooms"].append(
                (alt_presence, [rooms_dic[i].label for i in comb_rooms])
            )
            activities_alternative_ressources[aid]["teachers"].append(
                (alt_presence, [teachers_dic[i].label for i in comb_teachers])
            )
        model.AddExactlyOne(alt_presences)

    # START AFTER CONSTRAINTS
    for starts_after in starts_after_constraints:
        from_activities = starts_after.from_activity_group.activities
        from_activites_ids = [a.id for a in from_activities]
        to_activities = starts_after.to_activity_group.activities
        to_activities_ids = [a.id for a in to_activities]
        min_offset = starts_after.min_offset
        min_offset = int(min_offset / s_factor) if min_offset is not None else None
        max_offset = starts_after.max_offset
        max_offset = int(max_offset * s_factor) if max_offset is not None else None
        for from_id, to_id in itertools.product(from_activites_ids, to_activities_ids):
            from_end = activities_ends[from_id]
            to_start = activities_starts[to_id]
            if min_offset is not None:
                model.Add(to_start >= from_end + min_offset)
            if max_offset is not None:
                model.Add(to_start <= from_end + max_offset)

    # NO OVERLAP
    for teacher, intervals in teacher_intervals.items():
        if len(intervals) > 1:
            model.AddNoOverlap(intervals)
    for room, intervals in room_intervals.items():
        if len(intervals) > 1:
            model.AddNoOverlap(intervals)
    for student, intervals in atomic_students_intervals.items():
        if len(intervals) > 1:
            model.AddNoOverlap(intervals)

    return (
        activities_intervals,
        activities_starts,
        activities_ends,
        activities_durations,
        atomic_students_intervals,
        room_intervals,
        teacher_intervals,
        activities_alternative_ressources,
    )


def create_allowed_time_slots_per_kind(model, project, activities_starts):
    activity_kinds = project.activity_kinds
    horizon = project.horizon
    origin_monday = project.setup["ORIGIN_MONDAY"]
    origin_monday_slot = project.datetime_to_slot(origin_monday, round="floor")
    tspd = project.time_slots_per_day
    all_daily_slots = np.arange(tspd) + 1
    for akind in activity_kinds:
        activity_allowed_slots = akind.allowed_daily_start_slots
        activity_allowed_slots_ids = [s.id for s in activity_allowed_slots]
        activity_forbidden_slots = list(
            set(all_daily_slots) - set(activity_allowed_slots_ids)
        )
        for activity in akind.activities:
            aid = activity.id
            said = str(aid).zfill(4)
            start = activities_starts[aid]
            start_m96 = model.NewIntVar(-horizon, horizon, f"start_mod_{tspd}_{said}")
            model.AddModuloEquality(start_m96, start - origin_monday_slot, 96)
            for fslot in activity_forbidden_slots:
                model.Add(start_m96 != fslot)


def create_static_activities_overlap_constraints(
    project, atomic_students_intervals, teacher_intervals, room_intervals, model
):
    static_activities = project.static_activities
    atomic_students = project.atomic_students
    teachers = project.teachers
    rooms = project.rooms
    teacher_static_intervals = {t.id: [] for t in teachers}
    room_static_intervals = {r.id: [] for r in rooms}
    atomic_students_static_intervals = {s.id: [] for s in atomic_students}
    for static_activity in static_activities:
        start = static_activity.start
        end = static_activity.end
        duration = static_activity.duration
        aid = static_activity.id
        interval = model.NewIntervalVar(start, duration, end, f"static_activity_{aid}")
        if static_activity.students is not None:
            for atomic_student in static_activity.students.students:
                atomic_students_static_intervals[atomic_student.id].append(interval)
        for teacher in static_activity.allocated_teachers:
            teacher_static_intervals[teacher.id].append(interval)
        for room in static_activity.allocated_rooms:
            room_static_intervals[room.id].append(interval)

    for teacher, static_intervals in teacher_static_intervals.items():
        if len(static_intervals) > 1:
            for static_interval in static_intervals:
                for interval in teacher_intervals[teacher]:
                    model.AddNoOverlap([static_interval, interval])

    for room, static_intervals in room_static_intervals.items():
        if len(static_intervals) > 1:
            for static_interval in static_intervals:
                for interval in room_intervals[room]:
                    model.AddNoOverlap([static_interval, interval])

    for student, static_intervals in atomic_students_static_intervals.items():
        if len(static_intervals) > 1:
            for static_interval in static_intervals:
                for interval in atomic_students_intervals[student]:
                    model.AddNoOverlap([static_interval, interval])
    return (
        atomic_students_static_intervals,
        teacher_static_intervals,
        room_static_intervals,
    )


def create_weekly_unavailability_constraints(project, model, atomic_students_intervals):
    origin_monday = project.setup["ORIGIN_MONDAY"]
    origin_monday_slot = project.datetime_to_slot(origin_monday, round="floor")
    max_weeks = project.setup["MAX_WEEKS"]
    time_slots_per_week = project.setup["TIME_SLOTS_PER_WEEK"]  # 672
    horizon = project.setup["HORIZON"]

    weekly_unavailable_intervals = []
    weekly_unavailable_slots = (project.week_structure.T.flatten() == 0) * 1.0

    wusl, nlab = ndimage.label(weekly_unavailable_slots)
    wusl2 = [
        (s[0].start, s[0].stop) for s in ndimage.find_objects(wusl, max_label=nlab)
    ]

    for w in range(max_weeks):
        for (
            nint,
            interval,
        ) in enumerate(wusl2):
            start, stop = interval
            start_slot = origin_monday_slot + start + w * time_slots_per_week
            end_slot = origin_monday_slot + stop + w * time_slots_per_week
            if start_slot <= 0:
                start_slot = 0
            elif start_slot >= horizon:
                start_slot = horizon
            if end_slot <= start_slot:
                end_slot = 0
            elif end_slot >= horizon:
                end_slot = horizon
            duration = end_slot - start_slot
            if duration > 0:
                interval = model.NewIntervalVar(
                    start_slot,
                    duration,
                    end_slot,
                    f"weekly_unavailable_w{w+1}_interval{nint}",
                )
                weekly_unavailable_intervals.append(interval)

    for student, intervals in atomic_students_intervals.items():
        for sinterval in intervals:
            for interval in weekly_unavailable_intervals:
                model.AddNoOverlap([interval, sinterval])

    return weekly_unavailable_intervals


def export_solution_to_database(solver, engine, activities_starts, activities_alternative_ressources):
    session = Session(engine)
    project = session.execute(select(Project)).scalars().first()
    activities_dic = {a.id: a for a in project.activities}
    rooms_labels_dic = {r.label: r for r in project.rooms}
    teachers_labels_dic = {t.label: t for t in project.teachers}
    for aid, start in activities_starts.items():
        start_slot = solver.Value(start)
        activity = activities_dic[aid]
        activity.start = start_slot
        activity_alternative_ressources = activities_alternative_ressources[aid]
        activity.allocated_rooms = []
        for existance, alt_rooms_labels in activity_alternative_ressources["rooms"]:
            if solver.Value(existance) == 1:
                for room_label in alt_rooms_labels:
                    room = rooms_labels_dic[room_label]
                    activity.allocated_rooms.append(room)

        activity.allocated_teachers = []
        for existance, alt_teachers_labels in activity_alternative_ressources["teachers"]:
            if solver.Value(existance) == 1:
                for teacher_label in alt_teachers_labels:
                    teacher = teachers_labels_dic[teacher_label]
                    activity.allocated_teachers.append(teacher)
    session.commit()
    session.close()

def dump_solution(dump_dir, engine):    
    # engine = create_engine(setup["engine"], echo=False)
    # dump_dir = setup["dump_dir"]
    create_directory(dump_dir)
    Base.metadata.create_all(engine)
    session = Session(engine)
    project = session.execute(select(Project)).scalars().first()

    # DATA GATHERING
    existing_dumps = [f for f in os.listdir(dump_dir) if f.endswith(".csv")]
    existing_dumps = [f for f in existing_dumps if f.startswith("project_dump_")]
    if len(existing_dumps) == 0:
        max_dump = 0
    else:
        max_dump = max([int(f.split("_")[-1].split(".")[0]) for f in existing_dumps]) +1

    prefix = f"{dump_dir}/project_dump_{max_dump:04d}"

    # CSV
    out = {}
    for activity in project.activities:
        clabel = activity.course.label
        alabel = activity.label
        clabel = activity.course.label
        adata = {"start": activity.start, "start_datetime": activity.start_datetime.to_str()}
        adata["allocated_teachers_full"] = ";".join([t.full_name for t in activity.allocated_teachers])
        adata["allocated_teachers"] = ";".join([t.label for t in activity.allocated_teachers])
        adata["allocated_rooms"] = ";".join([r.label for r in activity.allocated_rooms])
        out[clabel, alabel] = adata

    out = pd.DataFrame(out).T
    out.to_csv(prefix + ".csv")
    print(f"Dumped to {prefix}.csv")
    session.close()