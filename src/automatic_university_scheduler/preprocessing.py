import numpy as np
import pandas as pd
import yaml
from automatic_university_scheduler.scheduling import Activity, Course
from automatic_university_scheduler.utils import create_directories
from automatic_university_scheduler.datetime import (
    TimeDelta,
    DateTime,
    datetime_to_slot,
)


# def courses_from_yml(yml_path, room_pools, default_rooms):
#     """
#     Parse a YAML file and create a dictionary of Course objects.

#     Parameters:
#     yml_path (str): The path to the YAML file.
#     room_pools (dict): A dictionary mapping room categories to lists of rooms.
#     default_rooms (dict): A dictionary mapping student counts to default rooms.

#     Returns:
#     dict: A dictionary mapping course labels to Course objects.
#     """
#     activities = {}
#     courses = {}
#     all_data = yaml.safe_load(open(yml_path))
#     for course_label, data in all_data.items():
#         course = Course(label=course_label, color=data["color"])
#         courses[course_label] = course
#         for label, activity in data["activities"].items():
#             act_kwargs = {"label": f"{course_label}_{label}"}
#             for key in [
#                 "min_start_slot",
#                 "max_start_slot",
#                 "early_start_slot",
#                 "latest_start_slot",
#                 "students",
#                 "duration",
#                 "kind",
#             ]:
#                 if key in activity.keys():
#                     act_kwargs[key] = activity[key]

#             act = Activity(**act_kwargs)
#             course.add_activity(act)
#             students = activity["students"]
#             activities[label] = act
#             for ressource in ["rooms", "teachers"]:
#                 pool_name = activity[ressource]["pool"]
#                 value = activity[ressource]["value"]
#                 if ressource == "rooms":
#                     pool = []
#                     for room_category in pool_name:
#                         if room_category == "default":
#                             pool += default_rooms[students]
#                         else:
#                             pool += room_pools[room_category]
#                 if ressource == "teachers":
#                     pool = [data["teachers_acronyms"][t] for t in pool_name]
#                 act.add_ressources(kind=ressource, quantity=value, pool=pool)

#         # CONSTRAINTS
#         inner_activity_groups = data["inner_activity_groups"]
#         if "foreign_activity_groups" in data.keys():
#             foreign_activity_groups = data["foreign_activity_groups"]
#         else:
#             foreign_activity_groups = {}
#         for constraint in data["constraints"]:

#             if constraint["kind"] == "succession":
#                 # print(constraint)
#                 start_groups = constraint["start_after"]
#                 end_groups = constraint["activities"]
#                 if "min_offset" in constraint.keys():
#                     min_offset = constraint["min_offset"]
#                 else:
#                     min_offset = 0
#                 if "max_offset" in constraint.keys():
#                     max_offset = constraint["max_offset"]
#                 else:
#                     max_offset = None
#                 for end_group in end_groups:
#                     end_activities = inner_activity_groups[end_group]
#                     for end_activity in end_activities:
#                         for start_group in start_groups:
#                             if start_group in inner_activity_groups.keys():
#                                 start_activities = inner_activity_groups[start_group]
#                                 inner_start = True
#                             elif start_group in foreign_activity_groups.keys():
#                                 start_activities = foreign_activity_groups[start_group]
#                                 inner_start = False
#                             # print(inner, start_group, "-->", end_group)
#                             if inner_start:
#                                 start_activities = [
#                                     activities[k]
#                                     for k in inner_activity_groups[start_group]
#                                 ]
#                                 activities[end_activity].add_multiple_after(
#                                     others=start_activities,
#                                     min_offset=min_offset,
#                                     max_offset=max_offset,
#                                 )
#                             else:
#                                 for start_activity in start_activities:
#                                     (
#                                         start_parent_label,
#                                         start_activity_label,
#                                     ) = start_activity
#                                     activities[end_activity].add_after_manual(
#                                         parent_label=start_parent_label,
#                                         activity_label=start_activity_label,
#                                         min_offset=min_offset,
#                                         max_offset=max_offset,
#                                     )
#     return courses


def create_course_activities(
    course_label,
    course_data,
    room_pools,
    default_rooms,
    teacher_full_names,
    origin_datetime,
    slot_duration,
):
    """
    Parse a YAML file and create a dictionary of Course objects.

    Parameters:
    yml_path (str): The path to the YAML file.
    room_pools (dict): A dictionary mapping room categories to lists of rooms.
    default_rooms (dict): A dictionary mapping student counts to default rooms.

    Returns:
    dict: A dictionary mapping course labels to Course objects.
    """
    activities = {}
    course = Course(label=course_label, color=course_data["color"])

    for label, activity in course_data["activities"].items():
        act_kwargs = {"label": f"{course_label}_{label}"}
        for key in [
            "min_start_slot",
            "max_start_slot",
            "students",
            "duration",
            "kind",
        ]:
            if key in activity.keys():
                act_kwargs[key] = activity[key]
        if "earliest_datetime" in activity.keys():
            earliest_datetime = DateTime.from_str(activity["earliest_datetime"])
            earliest_slot = datetime_to_slot(
                earliest_datetime, origin_datetime, slot_duration, round="ceil"
            )
            act_kwargs["min_start_slot"] = earliest_slot
        if "latest_datetime" in activity.keys():
            latest_datetime = DateTime.from_str(activity["latest_datetime"])
            latest_slot = datetime_to_slot(
                latest_datetime, origin_datetime, slot_duration, round="floor"
            )
            act_kwargs["max_start_slot"] = latest_slot
        act = Activity(**act_kwargs)
        course.add_activity(act)
        students = activity["students"]
        activities[label] = act
        for ressource in ["rooms", "teachers"]:
            pool_name = activity[ressource]["pool"]
            value = activity[ressource]["value"]
            if ressource == "rooms":
                pool = []
                for room_category in pool_name:
                    if room_category == "default":
                        pool += default_rooms[students]
                    else:
                        pool += room_pools[room_category]
            if ressource == "teachers":
                pool = [teacher_full_names[t] for t in pool_name]
            act.add_ressources(kind=ressource, quantity=value, pool=pool)

    # CONSTRAINTS
    inner_activity_groups = course_data["inner_activity_groups"]
    if "foreign_activity_groups" in course_data.keys():
        foreign_activity_groups = course_data["foreign_activity_groups"]
    else:
        foreign_activity_groups = {}
    for constraint in course_data["constraints"]:

        if constraint["kind"] == "succession":
            # print(constraint)
            start_groups = constraint["start_after"]
            end_groups = constraint["activities"]
            if "min_offset" in constraint.keys():
                min_offset = constraint["min_offset"]
            else:
                min_offset = 0
            if "max_offset" in constraint.keys():
                max_offset = constraint["max_offset"]
            else:
                max_offset = None
            for end_group in end_groups:
                end_activities = inner_activity_groups[end_group]
                for end_activity in end_activities:
                    for start_group in start_groups:
                        if start_group in inner_activity_groups.keys():
                            start_activities = inner_activity_groups[start_group]
                            inner_start = True
                        elif start_group in foreign_activity_groups.keys():
                            start_activities = foreign_activity_groups[start_group]
                            inner_start = False
                        # print(inner, start_group, "-->", end_group)
                        if inner_start:
                            start_activities = [
                                activities[k]
                                for k in inner_activity_groups[start_group]
                            ]
                            activities[end_activity].add_multiple_after(
                                others=start_activities,
                                min_offset=min_offset,
                                max_offset=max_offset,
                            )
                        else:
                            for start_activity in start_activities:
                                (
                                    start_parent_label,
                                    start_activity_label,
                                ) = start_activity
                                activities[end_activity].add_after_manual(
                                    parent_label=start_parent_label,
                                    activity_label=start_activity_label,
                                    min_offset=min_offset,
                                    max_offset=max_offset,
                                )
    return course


def read_week_structure_from_csv(path):
    """
    Reads a week structure from a CSV file and returns it as a 2D numpy array.

    The CSV file should have rows representing days and columns representing time slots.
    Each cell in the CSV file should contain a string of '0's and '1's,
    where '1' indicates that the corresponding time slot on the corresponding day is available,
    and '0' indicates that it is not.

    Parameters:
    path (str): The path to the CSV file.

    Returns:
    np.array: A 2D numpy array of integers representing the week structure.
              Each row corresponds to a day and each column corresponds to a time slot.
              A '1' indicates that the corresponding time slot on the corresponding day is available,
              and a '0' indicates that it is not.
    """
    return np.array(
        [
            list("".join(row))
            for row in pd.read_csv(path, index_col=0, header=0, dtype=str).values
        ],
        dtype=int,
    )


def get_unique_ressources_in_activities(data, kind="teachers"):
    """
    Extracts and returns the unique resources of a specified kind from the provided activity data.

    Parameters:
    data (dict): The activity data. This should be a dictionary where each key is a module name and
                 the corresponding value is a dictionary containing module data. The module data dictionary
                 should have an "activities" key whose value is another dictionary. This dictionary should
                 have keys that are activity names and values that are dictionaries containing activity data.
                 The activity data dictionary should have a key that matches the `kind` parameter and its
                 value should be a list of resources.
    kind (str, optional): The kind of resources to extract. This should match a key in the activity data
                          dictionaries. Defaults to "teachers".

    Returns:
    np.array: A numpy array containing the unique resources of the specified kind found in the activity data.
    """
    unique_ressources = []
    for module, mdata in data.items():
        for act_key, act in mdata["activities"].items():
            for ress in act[kind]:
                unique_ressources += ress[1]

    return np.unique(unique_ressources)


def get_unique_students_in_activities(data):
    """
    Extracts and returns the unique students from the provided activity data.

    Parameters:
    data (dict): The activity data. This should be a dictionary where each key is a module name and
                 the corresponding value is a dictionary containing module data. The module data dictionary
                 should have an "activities" key whose value is another dictionary. This dictionary should
                 have keys that are activity names and values that are dictionaries containing activity data.

    Returns:
    np.array: A numpy array containing the unique students found in the activity data.
    """
    unique_students = []
    for module, mdata in data.items():
        for act_key, act in mdata["activities"].items():
            unique_students.append(act["students"])

    return np.unique(unique_students)
