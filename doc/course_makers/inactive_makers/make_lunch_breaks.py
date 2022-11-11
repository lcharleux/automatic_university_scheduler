import json
import copy
import datetime

# LUNCH BREAKS
from automatic_university_scheduler.scheduling import (
    Activity,
    Course,
    isocalendar_to_slot,
)

START_DAY = datetime.date.fromisocalendar(2022, 36, 1)
slot_offset = 0
MAX_WEEKS = 10
students_groups = [
    "TPA1",
    "TPA2",
    "TPB1",
    "TPB2",
    "TPC1",
    "TPC2",
    "TPE1",
    "TPE2",
    "TPG1",
    "TPG2",
]


course_label = "Lunch_Break"
course = Course(label=course_label, color="gray")


def make_lunch_breaks(max_weeks, students_groups, add_to):
    activities = []
    for students in students_groups:
        for day in range(7 * max_weeks):

            activity = Activity(
                label=f"{course_label}_{students}_day{day}",
                students=students,
                kind="lunch",
                duration=4,
                min_start_slot=day * 96 + slot_offset,
                max_start_slot=(day + 1) * 96 + slot_offset,
            )
            activity.add_ressources(kind="teachers", quantity=0, pool=[])
            activity.add_ressources(kind="rooms", quantity=0, pool=[])
            course.add_activity(activity)
            if add_to != None:
                add_to.add_activity(activity)
            activities.append(activity)
    return activities


make_lunch_breaks(MAX_WEEKS, students_groups, course)
path = f"../activity_data/{course_label}.json"
with open(path, "w") as f:
    json.dump(course.to_dict(), f)
