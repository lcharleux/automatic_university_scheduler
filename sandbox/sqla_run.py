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
import pandas as pd

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


# STATIC ACTIVITIES


def extract_constraints_from_table(
    raw_data,
    project,
    format="USMB",
    school="POLYTECH Annecy",
):
    setup = project.setup
    # WEEK_STRUCTURE = setup["WEEK_STRUCTURE"]
    # WEEK_STRUCTURE = setup["WEEK_STRUCTURE"]
    # ORIGIN_DATETIME = setup["ORIGIN_DATETIME"]
    # HORIZON = setup["HORIZON"]
    TIME_SLOT_DURATION = setup["TIME_SLOT_DURATION"]
    # MAX_WEEKS = setup["MAX_WEEKS"]
    # TIME_SLOTS_PER_WEEK = setup["TIME_SLOTS_PER_WEEK"]

    # DAYS_PER_WEEK = setup["DAYS_PER_WEEK"]
    TIME_SLOTS_PER_DAY = setup["TIME_SLOTS_PER_DAY"]

    tracked_ressources = {
        "teachers": [t.full_name for t in project.teachers],
        "rooms": [r.label for r in project.rooms],
        "students": [s.label for s in project.students_groups],
    }
    ressources_dic = {
        "teachers": {t.full_name: t for t in project.teachers},
        "rooms": {r.label: r for r in project.rooms},
        "students": {s.label: s for s in project.students_groups},
    }
    if format == "USMB":
        slot_string_key = 'Chaîne qui référenence les créneaux occupés par tranche de 15mn de "00:00" à "23:45". (de gauche à droite car n°1 = plage de 00:00 à 00:15 -> car n°96 = plage de 23:45 à 00:00)'
        raw_data = raw_data[raw_data["Année"].isna() == False]  # REMOVE LAST EMPTY LINE

        def process_weekday(s):
            weekday_map = {
                "lundi": 1,
                "mardi": 2,
                "mercredi": 3,
                "jeudi": 4,
                "vendredi": 5,
                "samedi": 6,
                "dimanche": 7,
            }
            return weekday_map[s]

        def process_students_and_teachers(s):
            if type(s) == float:
                return ""
            else:
                return s.strip()

        col_map = {
            "year": lambda df: df["Année"].values.astype(np.int32),
            "week": lambda df: df["Semaine"].values.astype(np.int32),
            "weekday": lambda df: df["Jour"].map(process_weekday),
            "from_dayslot": lambda df: df[slot_string_key].map(lambda s: s.index("1")),
            "to_dayslot": lambda df: df[slot_string_key].map(
                lambda s: TIME_SLOTS_PER_DAY - s[::-1].index("1")
            ),
            "rooms": lambda df: df["Liste des salles"].map(
                lambda s: s.replace("Indéterminé", "")
            ),
            "students": lambda df: (df["Nom des groupes étudiants"]).map(
                process_students_and_teachers
            ),
            "teachers": lambda df: df["_Bloc Liste Enseignants (étape 4)"].map(
                process_students_and_teachers
            ),
            "school": lambda df: df["Composantes groupes étudiants"].map(
                lambda s: s.replace("Indéterminé", "")
            ),
            "description": lambda df: df["Libellé Activité"].map(
                process_students_and_teachers
            ),
        }

        data = {}
        for k, f in col_map.items():
            data[k] = f(raw_data)
        data = pd.DataFrame(data)

        constraints = {}
        static_activities_kwargs = []
        ignored_ressources = {"teachers": [], "rooms": [], "students": []}
        for kind in ["teachers", "rooms", "students"]:
            constraints[kind] = {
                r: {"unavailable": []} for r in tracked_ressources[kind]
            }
        # constraints["students"] = {
        #     r.id: {"unavailable": []} for r in project.students_groups if r != None
        # }

        for index, row in data.iterrows():
            start_time = TIME_SLOT_DURATION * row["from_dayslot"]
            start_time_seconds = start_time.total_seconds()
            start_time_hours = int(start_time_seconds // 3600)
            start_time_minutes = int(
                (start_time_seconds - start_time_hours * 3600) // 60
            )
            start_str = f"{row['year']}-W{ str(row['week']).zfill(2)}-{row['weekday']} {str(start_time_hours).zfill(2) }:{str(start_time_minutes).zfill(2)}"
            start_datetime = DT.from_str(start_str)
            end_time = TIME_SLOT_DURATION * row["to_dayslot"]
            end_time_seconds = end_time.total_seconds()
            end_time_hours = int(end_time_seconds // 3600)
            end_time_minutes = int((end_time_seconds - end_time_hours * 3600) // 60)
            end_str = f"{row['year']}-W{ str(row['week']).zfill(2)}-{row['weekday']} {str(end_time_hours).zfill(2) }:{str(end_time_minutes).zfill(2)}"
            end_datetime = DT.from_str(end_str)
            constraint = {
                "kind": "datetime",
                "start": start_datetime.to_str(),
                "end": end_datetime.to_str(),
                "label": row["description"],
            }
            start_slot = project.datetime_to_slot(start_datetime, round="floor")
            end_slot = project.datetime_to_slot(end_datetime, round="ceil")
            duration = end_slot - start_slot
            kwargs = {
                "kind": "Imported",
                "project": project,
                "start": start_slot,
                "duration": duration,
                "label": row["description"],
                "allocated_rooms": [],
                "allocated_teachers": [],
            }
            # OLD VERSION
            for kind in ["teachers", "students", "rooms"]:
                if kind == "students":
                    if row[kind] != "":
                        schools_names = row["school"]
                        if school in schools_names:
                            row_data = row[kind]
                        else:
                            row_data = ""
                    else:
                        row_data = ""
                else:
                    row_data = row[kind]

                if row_data != "":
                    ressources = [r.strip() for r in row_data.split(",")]
                    for ressource in ressources:
                        if ressource in tracked_ressources[kind]:
                            constraints[kind][ressource]["unavailable"].append(
                                constraint
                            )
                            if kind == "students":
                                kwargs["students"] = ressources_dic[kind][ressource]
                            elif kind == "teachers":
                                kwargs["allocated_teachers"].append(
                                    ressources_dic[kind][ressource]
                                )
                            elif kind == "rooms":
                                kwargs["allocated_rooms"].append(
                                    ressources_dic[kind][ressource]
                                )
                        else:
                            ignored_ressources[kind].append(ressource)
            static_activities_kwargs.append(kwargs)
            # NEW VERSION

        for kind in ["teachers", "rooms", "students"]:
            ignored_ressources[kind] = sorted(list(set(ignored_ressources[kind])))

        return (
            constraints,
            ignored_ressources,
            tracked_ressources,
            static_activities_kwargs,
        )


# Static Activities
existing_static_importerd_activities = (
    session.query(StaticActivity).where(StaticActivity.kind == "Imported").all()
)
for static_activity in existing_static_importerd_activities:
    session.delete(static_activity)
session.commit()

path = "filtered_data.csv"
existing_activities_dir = (
    "../doc/examples/basic_scheduling/existing_activities/extractions/"
)

if path.endswith(".xlsx"):
    raw_data = pd.read_excel(f"{existing_activities_dir}{path}", header=0)
elif path.endswith(".csv"):
    raw_data = pd.read_csv(f"{existing_activities_dir}{path}", header=0)
else:
    raise ValueError("Invalid file format")
(
    constraints,
    ignored_ressources,
    tracked_ressources,
    static_activities_kwargs,
) = extract_constraints_from_table(raw_data, project)

# Adding Imported Static Activities
for kwargs in static_activities_kwargs:

    static_activity = StaticActivity(**kwargs)
    session.add(static_activity)
    session.commit()

static_activities = session.execute(select(StaticActivity)).scalars().all()

# INTERVALS CREATION
for activity in activities:
    label = activity.label
    aid = activity.id
    said = str(aid).zfill(4)
    start = model.NewIntVar(0, horizon, f"start_{said}")
    end = model.NewIntVar(0, horizon, f"end_{said}")
    if activity.start != None:
        model.AddHint(start, activity.start)
    if activity.earliest_start_slot != None:
        model.Add(start >= activity.earliest_start_slot)
    if activity.latest_start_slot != None:
        model.Add(start <= activity.latest_start_slot)
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
solver.parameters.num_search_workers = 8
# solver.parameters.log_search_progress = True
# solver.fix_variables_to_their_hinted_value = True


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
        alabel = activities_dic[aid].label
        activity = activities_dic[aid]
        activity.start = start_slot
        start_datetime = activity.start_datetime

        print(f"Activity {aid} ({alabel}) starts at {start_slot} = {start_datetime}")

session.commit()
session.close()
