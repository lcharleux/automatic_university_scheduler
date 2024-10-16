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
)
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
import yaml
from ortools.sat.python import cp_model
import itertools
import numpy as np

setup = yaml.safe_load(open("setup.yaml"))


engine = create_engine(setup["engine"], echo=False)
Base.metadata.create_all(engine)


session = Session(engine)


project = session.execute(select(Project)).scalars().first()
activities = session.execute(select(Activity)).scalars().all()
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
HORIZON = project.horizon
TIME_SLOT_DURATION = project.time_slot_duration

# Existing activities : TODO

# Create constraints:
horizon = HORIZON
teacher_intervals = {t.id: [] for t in teachers}
room_intervals = {r.id: [] for r in rooms}
atomic_students_intervals = {s.id: [] for s in atomic_students}
activities_intervals = {}
activities_starts = {}
activities_ends = {}


# INTERVALS CREATION
for activity in activities:
    label = activity.label
    aid = activity.id
    said = str(aid).zfill(4)
    start = model.NewIntVar(0, HORIZON, f"start_{said}")
    end = model.NewIntVar(0, HORIZON, f"end_{said}")
    duration = activity.duration
    # model.Add(end == start + duration) # overkill ? Enforced by IntevalVar : https://developers.google.com/optimization/reference/python/sat/python/cp_model#newintervalvar
    interval = model.NewIntervalVar(start, duration, end, f"activity_{said}")
    atomic_students_ids = [i.id for i in activity.students.students]
    for sid in atomic_students_ids:
        atomic_students_intervals[sid].append(interval)
    activities_intervals[aid] = interval
    activities_starts[aid] = start
    activities_ends[aid] = end
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
        for fslot in activity_forbidden_slots:
            model.Add(start_m96 != fslot)
