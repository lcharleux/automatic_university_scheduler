import json
from sys import last_traceback

# MATH501


from scheduling import Activity, Course

n_TD = 14
course_label = "Math501"
course = Course(label=course_label, color="red")
TD_blocks = [
    ("TDA", "Math_teacher_1"),
    ("TDB", "Math_teacher_2"),
    ("TDC", "Math_teacher_1"),
    ("TDD", "Math_teacher_2"),
    ("TDE", "Math_teacher_1"),
    ("TDG", "Math_teacher_2"),
]
CM_rooms = ["Room_amphi_1", "Room_amphi_2"]
CC_rooms = ["Room_amphi_1", "Room_amphi_2"]
TD_rooms = ["TD_Room_1", "TD_Room_2", "TD_Room_3", "TD_Room_4", "TD_Room_5"]
last_act = None
students = "CM_TC"

# CM 1 2
for iact in range(1, 3):
    activity = Activity(label=f"{course_label}_{students}_{iact}", students=students)
    activity.add_ressources(kind="teachers", quantity=1, pool=["Math_teacher_1"])
    activity.add_ressources(kind="rooms", quantity=1, pool=CM_rooms)
    if last_act != None:
        activity.add_after(last_act, min_offset=10)
    if iact == 1:
        for group in ["TDAB", "TDD", "TDG"]:
            activity.add_after_manual(
                parent_label="Math500",
                activity_label=f"Math500_{group}_14",
                min_offset=10,
            )
    course.add_activity(activity)

    last_act = activity
last_cm = activity

# TD 1
last_TDs = []
n_Td = 1
for students, teacher in TD_blocks:
    last_act = None
    for iact in range(1, n_Td + 1):
        if iact == 1:
            last_act = last_cm
        activity = Activity(
            label=f"{course_label}_{students}_{iact}", students=students
        )
        activity.add_ressources(kind="teachers", quantity=1, pool=[teacher])
        activity.add_ressources(kind="rooms", quantity=1, pool=TD_rooms)
        if last_act != None:
            activity.add_after(last_act, min_offset=10)
        course.add_activity(activity)
        last_act = activity
        if iact == n_Td:
            last_TDs.append(activity)

# CM3
for iact in range(3, 4):
    activity = Activity(label=f"{course_label}_{students}_{iact}", students=students)
    activity.add_ressources(kind="teachers", quantity=1, pool=["Math_teacher_1"])
    activity.add_ressources(kind="rooms", quantity=1, pool=CM_rooms)
    for last_act in last_TDs:
        activity.add_after(last_act, min_offset=0)
    course.add_activity(activity)
    last_act = activity
last_cm = activity

with open(f"activity_data/{course_label}.json", "w") as f:
    json.dump(course.to_dict(), f)
