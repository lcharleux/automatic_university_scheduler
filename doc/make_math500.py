import json

# MATH500

from scheduling import Activity, Course

n_TD = 14
course_label = "Math500"
course = Course(label=course_label, color="red")
blocks = [
    ("TDAB", "Math_teacher_1"),
    ("TDD", "Math_teacher_2"),
    ("TDG", "Math_teacher_2"),
]
rooms = ["TD_Room_1", "TD_Room_2", "TD_Room_3", "TD_Room_4", "TD_Room_5"]
for students, teacher in blocks:
    last_act = None
    for iact in range(1, n_TD + 1):
        activity = Activity(
            label=f"{course_label}_{students}_{iact}", students=students
        )
        activity.add_ressources(kind="teachers", quantity=1, pool=[teacher])
        activity.add_ressources(kind="rooms", quantity=1, pool=rooms)
        if last_act != None:
            activity.add_after(last_act, min_offset=10)
        course.add_activity(activity)
        last_act = activity

with open("activity_data/math500.json", "w") as f:
    json.dump(course.to_dict(), f)
