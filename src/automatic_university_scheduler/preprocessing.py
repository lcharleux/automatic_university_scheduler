from automatic_university_scheduler.datetimeutils import DateTime as DT
from automatic_university_scheduler.datetimeutils import TimeDelta, datetime_to_slot
from automatic_university_scheduler.utils import create_instance
from automatic_university_scheduler.database import (
    DailySlot,
    Teacher,
    Room,
    Activity,
    ActivityGroup,
    StartsAfterConstraint,
    ActivityKind,
    WeekSlotsAvailabiblity,
    WeekDay,
    Course,
    StaticActivity,
    AtomicStudent,
    StudentsGroup,
    Manager,
    Planner,
)
import numpy as np
import itertools
import copy
import math
import datetime
import pandas as pd


def load_setup(data):
    """
    Load the setup file.
    """
    origin_datetime = DT.from_str(data["origin_datetime"])
    horizon_datetime = DT.from_str(data["horizon_datetime"])
    origin_monday = DT.fromisocalendar(
        origin_datetime.isocalendar().year, origin_datetime.isocalendar().week, 1
    )
    horizon_monday = DT.fromisocalendar(
        horizon_datetime.isocalendar().year, horizon_datetime.isocalendar().week, 1
    )
    out = {}
    out["WEEK_STRUCTURE"] = WEEK_STRUCTURE = read_week_structure(data["week_structure"])
    ONE_WEEK = TimeDelta.from_str("1w")
    ONE_DAY = TimeDelta.from_str("1d")
    out["DAYS_PER_WEEK"], out["TIME_SLOTS_PER_DAY"] = out["WEEK_STRUCTURE"].shape
    out["ORIGIN_DATETIME"] = origin_datetime
    out["HORIZON_DATETIME"] = horizon_datetime
    # out["HORIZON_MONDAY"] = horizon_monday
    # out["ORIGIN_MONDAY"] = origin_monday
    # out["MAX_WEEKS"] = (horizon_monday - origin_monday) // ONE_WEEK + 1
    out["TIME_SLOT_DURATION"] = ONE_DAY / out["TIME_SLOTS_PER_DAY"]
    out["TIME_SLOTS_PER_WEEK"] = out["DAYS_PER_WEEK"] * out["TIME_SLOTS_PER_DAY"]
    out["HORIZON"] = datetime_to_slot(
        horizon_datetime, origin_datetime, out["TIME_SLOT_DURATION"], round="floor"
    )
    out["ACTIVITIES_KINDS"] = data["activity_kinds"]
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


def process_constraint_static_activity(
    constraint, origin_datetime, horizon, time_slot_duration, **kwargs
):
    """
    Process a constraint and return a dictionary with the necessary information to create a StaticActivity object.
    """
    out = []
    if "repeat" not in constraint.keys():
        repeat = 1
        offset = 0
    else:
        repeat = constraint["repeat"]
        offset = constraint["offset"]
        if type(offset) == str:
            offset = TimeDelta.from_str(offset).to_slots(time_slot_duration)
    start0 = datetime_to_slot(
        DT.from_str(constraint["start"]),
        origin_datetime=origin_datetime,
        slot_duration=time_slot_duration,
        round="floor",
    )
    end0 = datetime_to_slot(
        DT.from_str(constraint["end"]),
        origin_datetime=origin_datetime,
        slot_duration=time_slot_duration,
        round="ceil",
    )
    for repeat in range(repeat):
        start = min(max(start0 + offset * repeat, 0), horizon)
        end = min(max(end0 + offset * repeat, 0), horizon)
        duration = end - start
        if duration > 0:
            dic = copy.copy(kwargs)
            dic["start"] = start
            dic["duration"] = duration
            out.append(dic)

    return out


def create_students(session, project, students_data):
    origin_datetime = project.origin_datetime
    time_slot_duration = project.time_slot_duration
    horizon = project.horizon
    atomic_students = {}
    students_groups = {}
    atomic_students_labels = set()
    students_groups_labels = set()
    for group, group_data in students_data["groups"].items():
        students_groups_labels.add(group)
        atomic_students_labels.update(group_data)
    for label in sorted(list(atomic_students_labels)):
        atomic_students[label] = create_instance(
            session, AtomicStudent, label=label, project=project, commit=True
        )
    for label in sorted(list(students_groups_labels)):
        students = np.array(
            [atomic_students[label] for label in students_data["groups"][label]]
        )
        labs = [s.label for s in students]
        students = (students[np.argsort(labs)]).tolist()
        students_groups[label] = create_instance(
            session,
            StudentsGroup,
            label=label,
            students=students,
            project=project,
            commit=True,
        )

    for group_label, group_data in students_data["constraints"].items():
        group = students_groups[group_label]
        if "unavailable" in group_data.keys():
            unvailable_data = group_data["unavailable"]
            for constraint in unvailable_data:
                if constraint["kind"] == "datetime":
                    if "label" in constraint.keys():
                        constraint_label = constraint["label"]
                    else:  # DEFAULT LABEL
                        constraint_label = "unavailable"
                    static_activity_kwargs = {
                        "project": project,
                        "kind": "students unavailable",
                        "students": group,
                        "label": constraint_label,
                    }
                    static_activities_kwargs = process_constraint_static_activity(
                        constraint=constraint,
                        origin_datetime=origin_datetime,
                        time_slot_duration=time_slot_duration,
                        horizon=horizon,
                        **static_activity_kwargs,
                    )
                    for static_activity_kwargs in static_activities_kwargs:
                        create_instance(
                            session,
                            StaticActivity,
                            **static_activity_kwargs,
                            commit=True,
                        )
    return atomic_students, students_groups


def create_daily_slots(session, project):
    """
    Create daily slots for a given project and time slot duration.
    """
    time_slot_duration = project.time_slot_duration
    daily_slots_dic = {}
    Ndslots = math.floor(datetime.timedelta(days=1) / time_slot_duration)
    slot = time_slot_duration * 0
    for i in range(Ndslots):
        dslot_label = slot.to_str()
        slot += time_slot_duration
        daily_slot = create_instance(
            session, DailySlot, label=dslot_label, project=project, commit=True
        )
        daily_slots_dic[i + 1] = daily_slot
    return daily_slots_dic


def create_teachers(session, project, teachers_data):
    time_slot_duration = project.time_slot_duration
    horizon = project.horizon
    origin_datetime = project.origin_datetime
    teachers = {}
    teachers_unavailable_static_activities = {}
    for label, teacher_data in teachers_data.items():
        full_name = teacher_data["full_name"]
        if "email" in teacher_data.keys():
            email = teacher_data["email"]
        else:
            email = ""
        teachers[label] = create_instance(
            session,
            Teacher,
            label=label,
            full_name=full_name,
            email=email,
            project=project,
            commit=True,
        )
        teachers_unavailable_static_activities[label] = []
        if "unavailable" in teacher_data.keys():
            for constraint in teacher_data["unavailable"]:
                static_activity_kwargs = {
                    "project": project,
                    "kind": "teacher unavailable",
                    "allocated_teachers": [teachers[label]],
                    "label": f"teacher {label} unavailable",
                }
                static_activities_kwargs = process_constraint_static_activity(
                    constraint=constraint,
                    origin_datetime=origin_datetime,
                    time_slot_duration=time_slot_duration,
                    horizon=horizon,
                    **static_activity_kwargs,
                )

                for static_activity_kwargs in static_activities_kwargs:
                    act = create_instance(
                        session, StaticActivity, **static_activity_kwargs, commit=True
                    )
                    teachers_unavailable_static_activities[label].append(act)
    return teachers, teachers_unavailable_static_activities


def create_managers(session, project, managers_data):
    managers = {}
    for label, manager_data in managers_data.items():
        full_name = manager_data["full_name"]
        if "email" in manager_data.keys():
            email = manager_data["email"]
        else:
            email = ""
        managers[label] = create_instance(
            session,
            Manager,
            label=label,
            full_name=full_name,
            email=email,
            project=project,
            commit=True,
        )
    return managers


def create_planners(session, project, planners_data):
    planners = {}
    for label, planner_data in planners_data.items():
        full_name = planner_data["full_name"]
        if "email" in planner_data.keys():
            email = planner_data["email"]
        else:
            email = ""
        planners[label] = create_instance(
            session,
            Planner,
            label=label,
            full_name=full_name,
            email=email,
            project=project,
            commit=True,
        )
    return planners


def create_activities_and_rooms(
    session,
    project,
    courses_data,
    room_pools,
    teachers,
    managers,
    planners,
    students_groups,
    activity_kinds,
):
    """ """
    duration_to_slots = project.duration_to_slots
    datetime_to_slot = project.datetime_to_slot
    rooms = {}
    activities_dic = {}
    activities_groups_dic = {}
    starts_after_constraint_dic = {}
    courses_dic = {}
    rooms_labels = set()

    for course_label, course_data in courses_data.items():
        activities = course_data["activities"]
        for activity, activity_data in activities.items():
            activity_room_pool = activity_data["rooms"]["pool"]
            if type(activity_room_pool) == str:
                room_pool = room_pools[activity_room_pool]
            else:
                room_pool = activity_data["rooms"]["pool"]
            teacher_pool = activity_data["teachers"]["pool"]
            rooms_labels.update(room_pool)
            activity_data["rooms"]["pool"] = room_pool

    for label in sorted(list(rooms_labels)):
        rooms[label] = create_instance(
            session, Room, label=label, project=project, capacity=30, commit=True
        )

    for course_label, course_data in courses_data.items():
        manager = managers[course_data["manager"]]
        planner = planners[course_data["planner"]]
        course = create_instance(
            session,
            Course,
            label=course_label,
            project=project,
            manager=manager,
            planner=planner,
            commit=True,
        )
        courses_dic[course_label] = course
        activities = course_data["activities"]
        for activity_label, activity_data in activities.items():
            activity_args = {
                "label": activity_label,
                "course": course,
                "project": project,
            }
            activity_args["kind"] = activity_kinds[activity_data["kind"]]
            activity_args["duration"] = duration_to_slots(activity_data["duration"])
            activity_args["room_pool"] = [
                rooms[l] for l in activity_data["rooms"]["pool"]
            ]
            activity_args["teacher_pool"] = [
                teachers[l] for l in activity_data["teachers"]["pool"]
            ]
            activity_args["teacher_count"] = activity_data["teachers"]["count"]
            activity_args["room_count"] = activity_data["rooms"]["count"]
            activity_args["students"] = students_groups[activity_data["students"]]
            if activity_args["teacher_count"] > len(activity_args["teacher_pool"]):
                raise ValueError(
                    f"Teacher count for activity {activity_label} is greater than the number of teachers in the pool"
                )
            if activity_args["room_count"] > len(activity_args["room_pool"]):
                raise ValueError(
                    f"Room count for activity {activity_label} is greater than the number of rooms in the pool"
                )
            # new_activity = Activity(**activity_args)
            if "earliest_start" in activity_data.keys():
                activity_args["earliest_start_slot"] = datetime_to_slot(
                    activity_data["earliest_start"], round="ceil"
                )
            if "latest_start" in activity_data.keys():
                activity_args["latest_start_slot"] = datetime_to_slot(
                    activity_data["latest_start"], round="floor"
                )
            new_activity = create_instance(
                session, Activity, **activity_args, commit=True
            )
            activities_dic[(course_label, activity_label)] = new_activity

    for course_label, course_data in courses_data.items():
        course = courses_dic[course_label]
        manager = managers[course_data["manager"]]
        planner = planners[course_data["planner"]]
        for group_label, group_data in course_data["inner_activity_groups"].items():

            gra = [activities_dic[(course_label, lab)] for lab in group_data]
            activity_group_kwargs = {
                "label": group_label,
                "activities": gra,
                "project": project,
                "course": course,
            }
            new_activity_group = create_instance(
                session, ActivityGroup, **activity_group_kwargs, commit=True
            )
            activities_groups_dic[(course_label, group_label)] = new_activity_group

        if "foreign_activity_groups" in course_data.keys():
            for group_label, group_data in course_data[
                "foreign_activity_groups"
            ].items():
                gra = [activities_dic[(clab, lab)] for clab, lab in group_data]
                activity_group_kwargs = {
                    "label": group_label,
                    "activities": gra,
                    "project": project,
                    "course": course,
                }
                new_activity_group = create_instance(
                    session, ActivityGroup, **activity_group_kwargs, commit=True
                )
                activities_groups_dic[(course_label, group_label)] = new_activity_group

        for constraints_data in course_data["constraints"]:
            if constraints_data["kind"] == "succession":
                from_act_groups_labels = constraints_data["start_after"]
                to_act_groups_labels = constraints_data["activities"]
                min_offset = constraints_data["min_offset"]
                if "max_offset" in constraints_data.keys():
                    max_offset = constraints_data["max_offset"]
                else:
                    max_offset = None
                for from_act_group_label, to_act_group_label in itertools.product(
                    from_act_groups_labels, to_act_groups_labels
                ):
                    from_act_group = activities_groups_dic[
                        (course_label, from_act_group_label)
                    ]
                    to_act_group = activities_groups_dic[
                        (course_label, to_act_group_label)
                    ]
                    starts_after_constraint_kwargs = {
                        "label": "starts_after",
                        "project": project,
                        "min_offset": duration_to_slots(min_offset),
                        "max_offset": duration_to_slots(max_offset),
                        "from_activity_group": from_act_group,
                        "to_activity_group": to_act_group,
                    }

                    cons = create_instance(
                        session,
                        StartsAfterConstraint,
                        **starts_after_constraint_kwargs,
                        commit=True,
                    )
                    starts_after_constraint_dic[cons.id] = cons
    return activities_dic, activities_groups_dic, rooms, starts_after_constraint_dic


def create_activity_kinds(session, project, activity_kinds, daily_slots_dic):
    out = {}
    for kind_label, kind_data in activity_kinds.items():
        kind_kwargs = {"session": session, "project": project, "label": kind_label}
        allowed_daily_start_slots = [
            daily_slots_dic[i] for i in kind_data["allowed_start_time_slots"]
        ]
        out[kind_label] = create_instance(
            allowed_daily_start_slots=allowed_daily_start_slots,
            cls=ActivityKind,
            **kind_kwargs,
            commit=True,
        )
    return out


def create_week_structure(session, project, week_structure, daily_slots, week_days):
    out = {}
    for (
        weekday,
        ddata,
    ) in enumerate(week_structure):
        for slot, value in enumerate(ddata):
            daily_slot = daily_slots[slot + 1]
            week_day = week_days[weekday + 1]
            available = value != 0
            out[(week_day.id, daily_slot.id)] = create_instance(
                session,
                WeekSlotsAvailabiblity,
                week_day_id=week_day.id,
                daily_slot_id=daily_slot.id,
                available=available,
                project=project,
            )
    return out


def create_weekdays(session, project):
    week_days = {}
    for i in range(7):
        days_names = [
            "monday",
            "tuesday",
            "wednesday",
            "thursday",
            "friday",
            "saturday",
            "sunday",
        ]
        week_days[i + 1] = create_instance(
            session, WeekDay, label=days_names[i], project=project
        )
    return week_days


def extract_constraints_from_table(
    raw_data,
    project,
    format="USMB",
    school="POLYTECH Annecy",
):
    setup = project.setup
    TIME_SLOT_DURATION = setup["TIME_SLOT_DURATION"]
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

        # constraints = {}
        static_activities_kwargs = []
        ignored_ressources = {"teachers": set(), "rooms": set(), "students": set()}
        # for kind in ["teachers", "rooms", "students"]:
        #     constraints[kind] = {
        #         r: {"unavailable": []} for r in tracked_ressources[kind]
        #     }

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
            start_slot = project.datetime_to_slot(start_datetime, round="floor")
            end_slot = project.datetime_to_slot(end_datetime, round="ceil")
            duration = end_slot - start_slot
            # BASIC STATIC ACTIVITY KWARGS
            kwargs = {
                "kind": "imported",
                "project": project,
                "start": start_slot,
                "duration": duration,
                "label": row["description"],
                "allocated_rooms": [],
                "allocated_teachers": [],
            }
            # RESSOURCES
            # 1. STUDENTS
            students_ressources = []
            students_str = None
            if row["students"] != "":
                schools_names = row["school"]
                if school in schools_names:
                    students_str = row["students"]
            if students_str is not None:
                students_list = [r.strip() for r in students_str.split(",")]
                for student in students_list:
                    if student in tracked_ressources["students"]:
                        students_ressources.append(ressources_dic["students"][student])
                    else:
                        ignored_ressources["students"].add(student)
            N_students = len(students_ressources)
            # 2. TEACHERS
            teachers_ressources = []
            teachers_str = row["teachers"]
            teachers_list = [r.strip() for r in teachers_str.split(",")]
            for teacher in teachers_list:
                if teacher in tracked_ressources["teachers"]:
                    teachers_ressources.append(ressources_dic["teachers"][teacher])
                else:
                    ignored_ressources["teachers"].add(teacher)
            N_teachers = len(teachers_ressources)
            # 3. ROOMS
            rooms_ressources = []
            rooms_str = row["rooms"]
            rooms_list = [r.strip() for r in rooms_str.split(",")]
            for room in rooms_list:
                if room in tracked_ressources["rooms"]:
                    rooms_ressources.append(ressources_dic["rooms"][room])
                else:
                    ignored_ressources["rooms"].add(room)
            N_rooms = len(rooms_ressources)
            # KWARGS PREPARATION
            kwargs["allocated_rooms"] = rooms_ressources
            kwargs["allocated_teachers"] = teachers_ressources
            if N_students > 0 or N_teachers > 0 or N_rooms > 0:
                if len(students_ressources) > 0:
                    for student_group in students_ressources:
                        kwargs2 = copy.copy(kwargs)
                        kwargs2["students"] = student_group
                        static_activities_kwargs.append(kwargs2)
                else:
                    kwargs2 = copy.copy(kwargs)
                    kwargs2["students"] = None
                    static_activities_kwargs.append(kwargs2)
        for kind in ["teachers", "rooms", "students"]:
            ignored_ressources[kind] = sorted(list(set(ignored_ressources[kind])))

    return (
        ignored_ressources,
        tracked_ressources,
        static_activities_kwargs,
    )
