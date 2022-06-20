import json
import copy

# MATH501


from scheduling import Activity, Course

n_TD = 14
course_label = "Math501"
course = Course(label=course_label, color="pink")
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


def make_CC(
    index=1,
    after=None,
    min_offset=0,
    add_to=None,
    teachers=["Math_Teacher_1", "Math_Teacher_2"],
    rooms=["Room_amphi_1", "Room_amphi_2"],
):
    students = "CM_TC"
    label = f"{course_label}_{students}_CC{index}"
    activity = Activity(label=label, students="CM_MM", kind="EX")
    activity.add_ressources(kind="teachers", quantity=2, pool=teachers)
    activity.add_ressources(kind="rooms", quantity=2, pool=CM_rooms)
    if after != None:
        for other in after:
            activity.add_after(other, min_offset=min_offset)
    if add_to != None:
        add_to.add_activity(activity)
    return activity


def make_CM(
    index=1,
    after=None,
    min_offset=0,
    add_to=None,
    teachers=["Math_Teacher_1"],
    rooms=["Room_amphi_1", "Room_amphi_2"],
):
    students = "CM_TC"
    label = f"{course_label}_{students}_CM{index}"
    activity = Activity(label=label, students="CM_MM", kind="CM")
    activity.add_ressources(kind="teachers", quantity=1, pool=teachers)
    activity.add_ressources(kind="rooms", quantity=1, pool=CM_rooms)
    if after != None:
        for other in after:
            activity.add_after(other, min_offset=min_offset)
    if add_to != None:
        add_to.add_activity(activity)
    return activity


def make_TD(TD_blocks, index=1, after=None, min_offset=0, add_to=None):
    activities = []
    for students, teacher in TD_blocks:
        activity = Activity(
            label=f"{course_label}_{students}_TD{index}", students=students
        )
        activity.add_ressources(kind="teachers", quantity=1, pool=[teacher])
        activity.add_ressources(kind="rooms", quantity=1, pool=TD_rooms)
        if after != None:
            for other in after:
                activity.add_after(other, min_offset=min_offset)
        course.add_activity(activity)
        if add_to != None:
            add_to.add_activity(activity)
        activities.append(activity)
    return activities


CC1 = make_CC(index=1, add_to=course)
for students in ["TDAB", "TDD", "TDG"]:
    CC1.add_after_manual(
        parent_label="Math500",
        activity_label=f"Math500_{students}_14",
        min_offset=10,
    )

CM1 = make_CM(index=1, after=[CC1], add_to=course)
CM2 = make_CM(index=2, after=[CM1], add_to=course)
TD1s = make_TD(TD_blocks, index=1, after=[CM2], min_offset=0, add_to=course)
CM3 = make_CM(index=3, after=TD1s, add_to=course)
TD2s = make_TD(TD_blocks, index=2, after=[CM3], min_offset=0, add_to=course)
CM4 = make_CM(index=4, after=TD2s, add_to=course)
TD3s = make_TD(TD_blocks, index=3, after=[CM4], min_offset=0, add_to=course)
CM5 = make_CM(index=5, after=TD3s, add_to=course)
TD4s = make_TD(TD_blocks, index=4, after=[CM5], min_offset=0, add_to=course)
CM6 = make_CM(index=6, after=TD4s, add_to=course)
TD5s = make_TD(TD_blocks, index=5, after=[CM6], min_offset=0, add_to=course)
CM7 = make_CM(index=7, after=TD5s, add_to=course)
TD6s = make_TD(TD_blocks, index=6, after=[CM7], min_offset=0, add_to=course)
CM8 = make_CM(index=8, after=TD6s, add_to=course)
CC2 = make_CC(index=2, after=[CM8], add_to=course)
TD7s = make_TD(TD_blocks, index=7, after=[CC2], min_offset=0, add_to=course)
CM9 = make_CM(index=9, after=TD7s, add_to=course)
TD8s = make_TD(TD_blocks, index=8, after=[CM9], min_offset=0, add_to=course)
CM10 = make_CM(index=10, after=TD8s, add_to=course)
TD9s = make_TD(TD_blocks, index=9, after=[CM10], min_offset=0, add_to=course)
CM11 = make_CM(index=11, after=TD9s, add_to=course)
TD10s = make_TD(TD_blocks, index=10, after=[CM11], min_offset=0, add_to=course)
CM12 = make_CM(index=12, after=TD10s, add_to=course)
TD11s = make_TD(TD_blocks, index=11, after=[CM12], min_offset=0, add_to=course)
CM13 = make_CM(index=13, after=TD11s, add_to=course)
TD12s = make_TD(TD_blocks, index=12, after=[CM13], min_offset=0, add_to=course)
CM14 = make_CM(index=14, after=TD12s, add_to=course)
TD13s = make_TD(TD_blocks, index=13, after=[CM14], min_offset=0, add_to=course)
CC3 = make_CC(index=3, after=TD13s, add_to=course)

path = f"activity_data/{course_label}.json"
with open(path, "w") as f:
    json.dump(course.to_dict(), f)
