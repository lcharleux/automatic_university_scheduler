from automatic_university_scheduler.datetimeutils import datetime_to_slot, TimeDelta
from automatic_university_scheduler.datetimeutils import DateTime as DT
from automatic_university_scheduler.utils import create_instance
import math
import datetime
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
)
import numpy as np
import itertools
import copy


# def process_constraint_static_activity(
#     constraint, origin_datetime, horizon, time_slot_duration, **kwargs
# ):
#     """
#     Process a constraint and return a dictionary with the necessary information to create a StaticActivity object.
#     """
#     out = []
#     if "repeat" not in constraint.keys():
#         repeat = 1
#         offset = 0
#     else:
#         repeat = constraint["repeat"]
#         offset = constraint["offset"]
#         if type(offset) == str:
#             offset = TimeDelta.from_str(offset).to_slots(time_slot_duration)
#     start0 = datetime_to_slot(
#         DT.from_str(constraint["start"]),
#         origin_datetime=origin_datetime,
#         slot_duration=time_slot_duration,
#         round="floor",
#     )
#     end0 = datetime_to_slot(
#         DT.from_str(constraint["end"]),
#         origin_datetime=origin_datetime,
#         slot_duration=time_slot_duration,
#         round="ceil",
#     )
#     for repeat in range(repeat):
#         start = min(max(start0 + offset * repeat, 0), horizon)
#         end = min(max(end0 + offset * repeat, 0), horizon)
#         duration = end - start
#         if duration > 0:
#             dic = copy.copy(kwargs)
#             dic["start"] = start
#             dic["duration"] = duration
#             out.append(dic)

#     return out


# def create_students(session, project, students_data):
#     origin_datetime = project.origin_datetime
#     time_slot_duration = project.time_slot_duration
#     horizon = project.horizon
#     atomic_students = {}
#     students_groups = {}
#     atomic_students_labels = set()
#     students_groups_labels = set()
#     for group, group_data in students_data["groups"].items():
#         students_groups_labels.add(group)
#         atomic_students_labels.update(group_data)
#     for label in sorted(list(atomic_students_labels)):
#         atomic_students[label] = create_instance(
#             session, AtomicStudent, label=label, project=project, commit=True
#         )
#     for label in sorted(list(students_groups_labels)):
#         students = np.array(
#             [atomic_students[label] for label in students_data["groups"][label]]
#         )
#         labs = [s.label for s in students]
#         students = (students[np.argsort(labs)]).tolist()
#         students_groups[label] = create_instance(
#             session,
#             StudentsGroup,
#             label=label,
#             students=students,
#             project=project,
#             commit=True,
#         )

#     for group_label, group_data in students_data["constraints"].items():
#         group = students_groups[group_label]
#         if "unavailable" in group_data.keys():
#             unvailable_data = group_data["unavailable"]
#             for constraint in unvailable_data:
#                 if constraint["kind"] == "datetime":
#                     static_activity_kwargs = {
#                         "project": project,
#                         "kind": "students unavailable",
#                         "students": group,
#                         "label": "unavailable",
#                     }
#                     static_activities_kwargs = process_constraint_static_activity(
#                         constraint=constraint,
#                         origin_datetime=origin_datetime,
#                         time_slot_duration=time_slot_duration,
#                         horizon=horizon,
#                         **static_activity_kwargs,
#                     )
#                     for static_activity_kwargs in static_activities_kwargs:
#                         create_instance(
#                             session,
#                             StaticActivity,
#                             **static_activity_kwargs,
#                             commit=True,
#                         )
#     return atomic_students, students_groups


# def create_daily_slots(session, project):
#     """
#     Create daily slots for a given project and time slot duration.
#     """
#     time_slot_duration = project.time_slot_duration
#     daily_slots_dic = {}
#     Ndslots = math.floor(datetime.timedelta(days=1) / time_slot_duration)
#     slot = time_slot_duration * 0
#     for i in range(Ndslots):
#         dslot_label = slot.to_str()
#         slot += time_slot_duration
#         daily_slot = create_instance(
#             session, DailySlot, label=dslot_label, project=project, commit=True
#         )
#         daily_slots_dic[i + 1] = daily_slot
#     return daily_slots_dic


# def create_teachers(session, project, teachers_data):
#     time_slot_duration = project.time_slot_duration
#     horizon = project.horizon
#     origin_datetime = project.origin_datetime
#     teachers = {}
#     teachers_unavailable_static_activities = {}
#     for label, teacher_data in teachers_data.items():
#         full_name = teacher_data["full_name"]
#         teachers[label] = create_instance(
#             session,
#             Teacher,
#             label=label,
#             full_name=full_name,
#             project=project,
#             commit=True,
#         )
#         teachers_unavailable_static_activities[label] = []
#         for constraint in teacher_data["unavailable"]:
#             static_activity_kwargs = {
#                 "project": project,
#                 "kind": "teacher unavailable",
#                 "allocated_teachers": [teachers[label]],
#                 "label": f"teacher {label} unavailable",
#             }
#             static_activities_kwargs = process_constraint_static_activity(
#                 constraint=constraint,
#                 origin_datetime=origin_datetime,
#                 time_slot_duration=time_slot_duration,
#                 horizon=horizon,
#                 **static_activity_kwargs,
#             )

#             for static_activity_kwargs in static_activities_kwargs:
#                 act = create_instance(
#                     session, StaticActivity, **static_activity_kwargs, commit=True
#                 )
#                 teachers_unavailable_static_activities[label].append(act)
#     return teachers, teachers_unavailable_static_activities


# def create_activities_and_rooms(
#     session, project, courses_data, teachers, students_groups, activity_kinds
# ):
#     """ """
#     duration_to_slots = project.duration_to_slots
#     datetime_to_slot = project.datetime_to_slot
#     rooms = {}
#     activities_dic = {}
#     activities_groups_dic = {}
#     starts_after_constraint_dic = {}
#     rooms_labels = set()

#     for course_label, course_data in courses_data.items():
#         activities = course_data["activities"]
#         for activity, activity_data in activities.items():
#             room_pool = activity_data["rooms"]["pool"]
#             teacher_pool = activity_data["teachers"]["pool"]
#             rooms_labels.update(room_pool)

#     for label in sorted(list(rooms_labels)):
#         rooms[label] = create_instance(
#             session, Room, label=label, project=project, capacity=30, commit=True
#         )

#     for course_label, course_data in courses_data.items():
#         course = create_instance(
#             session, Course, label=course_label, project=project, commit=True
#         )
#         activities = course_data["activities"]
#         for activity_label, activity_data in activities.items():
#             activity_args = {
#                 "label": activity_label,
#                 "course": course,
#                 "project": project,
#             }
#             activity_args["kind"] = activity_kinds[activity_data["kind"]]
#             activity_args["duration"] = duration_to_slots(activity_data["duration"])
#             activity_args["room_pool"] = [
#                 rooms[l] for l in activity_data["rooms"]["pool"]
#             ]
#             activity_args["teacher_pool"] = [
#                 teachers[l] for l in activity_data["teachers"]["pool"]
#             ]
#             activity_args["students"] = students_groups[activity_data["students"]]
#             # new_activity = Activity(**activity_args)
#             if "earliest_start" in activity_data.keys():
#                 activity_args["earliest_start_slot"] = datetime_to_slot(
#                     activity_data["earliest_start"], round="ceil"
#                 )
#             if "latest_start" in activity_data.keys():
#                 activity_args["latest_start_slot"] = datetime_to_slot(
#                     activity_data["latest_start"], round="floor"
#                 )
#             new_activity = create_instance(
#                 session, Activity, **activity_args, commit=True
#             )
#             activities_dic[(course_label, activity_label)] = new_activity
#         for group_label, group_data in course_data["inner_activity_groups"].items():

#             gra = [activities_dic[(course_label, l)] for l in group_data]
#             activity_group_kwargs = {
#                 "label": group_label,
#                 "activities": gra,
#                 "project": project,
#                 "course": course,
#             }
#             new_activity_group = create_instance(
#                 session, ActivityGroup, **activity_group_kwargs, commit=True
#             )
#             activities_groups_dic[(course_label, group_label)] = new_activity_group
#         for constraints_data in course_data["constraints"]:
#             if constraints_data["kind"] == "succession":
#                 from_act_groups_labels = constraints_data["start_after"]
#                 to_act_groups_labels = constraints_data["activities"]
#                 min_offset = constraints_data["min_offset"]
#                 if "max_offset" in constraints_data.keys():
#                     max_offset = constraints_data["max_offset"]
#                 else:
#                     max_offset = None
#                 for from_act_group_label, to_act_group_label in itertools.product(
#                     from_act_groups_labels, to_act_groups_labels
#                 ):
#                     from_act_group = activities_groups_dic[
#                         (course_label, from_act_group_label)
#                     ]
#                     to_act_group = activities_groups_dic[
#                         (course_label, to_act_group_label)
#                     ]
#                     starts_after_constraint_kwargs = {
#                         "label": "starts_after",
#                         "project": project,
#                         "min_offset": duration_to_slots(min_offset),
#                         "max_offset": duration_to_slots(max_offset),
#                         "from_activity_group": from_act_group,
#                         "to_activity_group": to_act_group,
#                     }

#                     cons = create_instance(
#                         session,
#                         StartsAfterConstraint,
#                         **starts_after_constraint_kwargs,
#                         commit=True,
#                     )
#                     starts_after_constraint_dic[cons.id] = cons
#     return activities_dic, activities_groups_dic, rooms, starts_after_constraint_dic


# def create_activity_kinds(session, project, activity_kinds, daily_slots_dic):
#     out = {}
#     for kind_label, kind_data in activity_kinds.items():
#         kind_kwargs = {"session": session, "project": project, "label": kind_label}
#         allowed_daily_start_slots = [
#             daily_slots_dic[i] for i in kind_data["allowed_start_time_slots"]
#         ]
#         out[kind_label] = create_instance(
#             allowed_daily_start_slots=allowed_daily_start_slots,
#             cls=ActivityKind,
#             **kind_kwargs,
#             commit=True,
#         )
#     return out


# def create_week_structure(session, project, week_structure, daily_slots, week_days):
#     out = {}
#     for (
#         weekday,
#         ddata,
#     ) in enumerate(week_structure):
#         for slot, value in enumerate(ddata):
#             daily_slot = daily_slots[slot + 1]
#             week_day = week_days[weekday + 1]
#             available = value != 0
#             out[(week_day.id, daily_slot.id)] = create_instance(
#                 session,
#                 WeekSlotsAvailabiblity,
#                 week_day_id=week_day.id,
#                 daily_slot_id=daily_slot.id,
#                 available=available,
#                 project=project,
#             )
#     return out


# def create_weekdays(session, project):
#     week_days = {}
#     for i in range(7):
#         days_names = [
#             "monday",
#             "tuesday",
#             "wednesday",
#             "thursday",
#             "friday",
#             "saturday",
#             "sunday",
#         ]
#         week_days[i + 1] = create_instance(
#             session, WeekDay, label=days_names[i], project=project
#         )
#     return week_days
