from ortools.sat.python import cp_model
from automatic_university_scheduler.database import StaticActivity
import itertools
import numpy as np
from scipy import ndimage


def absolute_week_duration_deviation(
    project, model, activities_starts, activities_durations
):
    """ """
    setup = project.setup
    max_weeks = setup["MAX_WEEKS"]
    time_slots_per_week = setup["TIME_SLOTS_PER_WEEK"]
    horizon = setup["HORIZON"]
    students_groups_ids = [g.id for g in project.atomic_students]
    week_duration = {gid: [[] for i in range(max_weeks)] for gid in students_groups_ids}
    total_activities_duration = {gid: 0 for gid in students_groups_ids}
    for aid, start in activities_starts.items():
        week = model.NewIntVar(0, max_weeks, "makespan")
        model.AddDivisionEquality(week, start, time_slots_per_week)
        duration = activities_durations[aid]
        for i in range(max_weeks):
            is_week = model.NewBoolVar("is_week")
            model.Add(week == i).OnlyEnforceIf(is_week)
            model.Add(week != i).OnlyEnforceIf(is_week.Not())
            duration_on_week = model.NewIntVar(
                0, time_slots_per_week, "duration_on_week"
            )
            model.Add(duration_on_week == duration).OnlyEnforceIf(is_week)
            model.Add(duration_on_week == 0).OnlyEnforceIf(is_week.Not())
            for gid in students_groups_ids:
                week_duration[gid][i].append(duration_on_week)
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
            0, time_slots_per_week, f"mean_week_duration_{group}"
        )
        model.AddDivisionEquality(
            mean_week_duration, total_activities_duration[group], len(wd)
        )
        for w in wd:
            week_duration = sum(w)
            abs_week_residual = model.NewIntVar(
                0, time_slots_per_week, "mean_week_duration"
            )
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
    value = model.NewIntVar(0, horizon, "makespan")
    model.Add(value == sum(week_duration_residuals))
    return value


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
                (alt_presence, [rooms_dic[i] for i in comb_rooms])
            )
            activities_alternative_ressources[aid]["teachers"].append(
                (alt_presence, [teachers_dic[i] for i in comb_teachers])
            )
        model.AddExactlyOne(alt_presences)

    # START AFTER CONSTRAINTS
    for starts_after in starts_after_constraints:
        from_activities = starts_after.from_activity_group.activities
        from_activites_ids = [a.id for a in from_activities]
        to_activities = starts_after.to_activity_group.activities
        to_activities_ids = [a.id for a in to_activities]
        min_offset = starts_after.min_offset
        max_offset = starts_after.max_offset
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
