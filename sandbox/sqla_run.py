from classes import (
    Base,
    Room,
    Activity,
    StudentsGroup,
    AtomicStudent,
    Project,
    Teacher,
    StartsAfterConstraint,
    ActivityGroup,
    ActivityKind,
    absolute_week_duration_deviation,
    StaticActivity,
)
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
import yaml
from ortools.sat.python import cp_model
import itertools
import numpy as np
from automatic_university_scheduler.datetimeutils import DateTime as DT
from automatic_university_scheduler.utils import Messages
from automatic_university_scheduler.scheduling import SolutionPrinter
from automatic_university_scheduler.datetimeutils import slot_to_datetime
import time

setup = yaml.safe_load(open("setup.yaml"))


engine = create_engine(setup["engine"], echo=False)
Base.metadata.create_all(engine)


session = Session(engine)


project = session.execute(select(Project)).scalars().first()
activities = session.execute(select(Activity)).scalars().all()
static_activities = session.execute(select(StaticActivity)).scalars().all()
students_groups = session.execute(select(StudentsGroup)).scalars().all()
atomic_students = session.execute(select(AtomicStudent)).scalars().all()
rooms = session.execute(select(Room)).scalars().all()
teachers = session.execute(select(Teacher)).scalars().all()
activity_kinds = session.execute(select(ActivityKind)).scalars().all()
starts_after_constraints = (
    session.execute(select(StartsAfterConstraint)).scalars().all()
)


# MODEL CREATION
model = cp_model.CpModel()
setup = project.setup
horizon = setup["HORIZON"]
time_slot_duration = setup["TIME_SLOT_DURATION"]

# Existing activities : TODO

# Create constraints:
# horizon = HORIZON
teacher_intervals = {t.id: [] for t in teachers}
teacher_static_intervals = {t.id: [] for t in teachers}
room_intervals = {r.id: [] for r in rooms}
room_static_intervals = {r.id: [] for r in rooms}
atomic_students_intervals = {s.id: [] for s in atomic_students}
atomic_students_static_intervals = {s.id: [] for s in atomic_students}
activities_intervals = {}
activities_starts = {}
activities_ends = {}
activities_durations = {}


# INTERVALS CREATION
for activity in activities:
    label = activity.label
    aid = activity.id
    said = str(aid).zfill(4)
    start = model.NewIntVar(0, horizon, f"start_{said}")
    end = model.NewIntVar(0, horizon, f"end_{said}")
    duration = activity.duration
    # model.Add(end == start + duration) # overkill ? Enforced by IntevalVar : https://developers.google.com/optimization/reference/python/sat/python/cp_model#newintervalvar
    interval = model.NewIntervalVar(start, duration, end, f"activity_{said}")
    atomic_students_ids = [i.id for i in activity.students.students]
    for sid in atomic_students_ids:
        atomic_students_intervals[sid].append(interval)
    activities_intervals[aid] = interval
    activities_starts[aid] = start
    activities_ends[aid] = end
    activities_durations[aid] = duration
    # ALTERNATIVES
    items = []
    kind = []
    alt_presences = []

    room_pool = activity.room_pool
    room_pool_ids = [r.id for r in room_pool]
    room_pool_dic = {r.id: r for r in room_pool}
    room_count = activity.room_count
    items.append(itertools.combinations(room_pool_ids, room_count))
    kind.append("room")
    teacher_pool = activity.teacher_pool
    teacher_pool_ids = [t.id for t in teacher_pool]
    teacher_pool_dic = {t.id: t for t in teacher_pool}
    teacher_count = activity.teacher_count
    items.append(itertools.combinations(teacher_pool_ids, teacher_count))
    kind.append("teacher")
    combinations = [p for p in itertools.product(*items)]
    for icomb, combination in enumerate(combinations):
        comb_rooms = np.concatenate(
            [combination[i] for i in range(len(combination)) if kind[i] == "room"]
        )
        comb_teachers = np.concatenate(
            [combination[i] for i in range(len(combination)) if kind[i] == "teacher"]
        )
        alt_presence = model.NewBoolVar(f"presence_{said}_alt{icomb}")
        alt_start = model.NewIntVar(0, horizon, f"start_{said}_alt{icomb}")
        alt_end = model.NewIntVar(0, horizon, f"end_{said}_alt{icomb}")
        model.Add(alt_end == alt_start + duration)
        alt_interval = model.NewOptionalIntervalVar(
            alt_start, duration, alt_end, alt_presence, f"activity_{said}_alt{icomb}"
        )
        model.Add(start == alt_start).OnlyEnforceIf(alt_presence)
        # model.Add(end == alt_end).OnlyEnforceIf(alt_presence) # overkill ?
        alt_presences.append(alt_presence)
        for tid in comb_teachers:
            teacher_intervals[tid].append(alt_interval)
        for rid in comb_rooms:
            room_intervals[rid].append(alt_interval)
    model.AddExactlyOne(alt_presences)

for starts_after in starts_after_constraints:
    from_activities = starts_after.from_activity_group.activities
    from_activites_ids = [a.id for a in from_activities]
    to_activities = starts_after.to_activity_group.activities
    to_activities_ids = [a.id for a in to_activities]
    min_offset = starts_after.min_offset
    max_offset = starts_after.max_offset
    for from_id, to_id in itertools.product(from_activites_ids, to_activities_ids):
        from_end = activities_ends[from_id]
        to_start = activities_ends[to_id]
        if min_offset != None:
            model.Add(to_start >= from_end + min_offset)
        if max_offset != None:
            model.Add(to_start <= from_end + min_offset)


# ALLOWED TIME SLOTS PER KIND
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
        start_m96 = model.NewIntVar(1, horizon, f"start_mod_{tspd}_{said}")
        model.AddModuloEquality(start_m96, start, 96)
        for fslot in activity_forbidden_slots:
            model.Add(start_m96 != fslot)

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

# UNAVAILABILITY
for static_activity in static_activities:
    start = static_activity.start
    end = static_activity.end
    duration = static_activity.duration
    aid = static_activity.id
    said = str(aid).zfill(4)
    interval = model.NewIntervalVar(start, duration, end, f"static_activity_{aid}")
    if static_activity.students != None:
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

# for room, static_interval in room_static_intervals.items():
#     if len(intervals) > 1:
#         for interval in room_intervals[room]:
#             model.AddNoOverlap([static_interval, interval])

# for student, static_interval in atomic_students_static_intervals.items():
#     if len(intervals) > 1:
#         for interval in atomic_students_intervals[student]:
#             model.AddNoOverlap([static_interval, interval])

# COST FUNCTION


value = absolute_week_duration_deviation(
    project, model, activities_starts, activities_durations
)

model.Minimize(value)
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

setup = project.setup
if not solver_final_status == "INFEASIBLE":
    activities_dic = {a.id: a for a in activities}
    for aid, start in activities_starts.items():
        start_slot = solver.Value(start)
        start_datetime = slot_to_datetime(
            start_slot, setup["ORIGIN_DATETIME"], setup["TIME_SLOT_DURATION"]
        )
        alabel = activities_dic[aid].label
        print(f"Activity {aid} ({alabel}) starts at {start_slot} = {start_datetime}")
