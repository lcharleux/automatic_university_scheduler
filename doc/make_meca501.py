import json
import copy

# MATH501


from scheduling import Activity, Course

n_TD = 14
course_label = "Meca501"
course = Course(label=course_label, color="gray")
TD_blocks = [
    ("TDA", "Teacher_ER"),
    ("TDB", "Teacher_ER"),
    ("TDC", "Teacher_ER"),
]
CM_rooms = ["Room_amphi_1", "Room_amphi_2"]
CC_rooms = ["Room_amphi_1", "Room_amphi_2"]
TD_rooms = [
    "TD_Room_1",
    "TD_Room_2",
    "TD_Room_3",
    "TD_Room_4",
    "TD_Room_5",
    "TD_Room_6",
]
last_act = None
students = "CM_TC"


def make_CC(
    index=1,
    after=None,
    min_offset=0,
    add_to=None,
    teachers=["Teacher_ER"],
    rooms=["Room_amphi_1", "Room_amphi_2"],
):
    students = "CM_TC"
    label = f"{course_label}_{students}_CC{index}"
    activity = Activity(label=label, students="CM_MM", kind="EX")
    activity.add_ressources(kind="teachers", quantity=1, pool=teachers)
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
    teachers=["Teacher_ER"],
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


"""CC1 = make_CC(index=1, add_to=course)
for students in ["TDAB", "TDD", "TDG"]:
    CC1.add_after_manual(
        parent_label="Math500",
        activity_label=f"Math500_{students}_14",
        min_offset=10,
    )"""

CM1 = make_CM(index=1, add_to=course)
CM2 = make_CM(index=2, after=[CM1], add_to=course)
CM3 = make_CM(index=3, after=[CM2], add_to=course)

TD1s = make_TD(TD_blocks, index=1, after=[CM3], min_offset=0, add_to=course)
CM4 = make_CM(index=4, after=TD1s, add_to=course)
TD2s = make_TD(TD_blocks, index=2, after=[CM4], min_offset=0, add_to=course)
CM5 = make_CM(index=5, after=TD2s, add_to=course)
TD3s = make_TD(TD_blocks, index=3, after=[CM5], min_offset=0, add_to=course)
CM6 = make_CM(index=6, after=TD3s, add_to=course)

TD4s = make_TD(TD_blocks, index=4, after=[CM6], min_offset=0, add_to=course)
CM7 = make_CM(index=7, after=TD4s, add_to=course)

TD5s = make_TD(TD_blocks, index=5, after=[CM7], min_offset=0, add_to=course)
CM8 = make_CM(index=8, after=TD5s, add_to=course)
TD6s = make_TD(TD_blocks, index=6, after=[CM8], min_offset=0, add_to=course)

CM9 = make_CM(index=9, after=TD6s, add_to=course)
CC1 = make_CC(index=1, after=[CM9], add_to=course)

TD7s = make_TD(TD_blocks, index=7, after=[CC1], min_offset=0, add_to=course)
CM10 = make_CM(index=10, after=TD7s, add_to=course)
TD8s = make_TD(TD_blocks, index=8, after=[CM10], min_offset=0, add_to=course)
TD9s = make_TD(TD_blocks, index=9, after=TD8s, min_offset=0, add_to=course)
TD10s = make_TD(TD_blocks, index=10, after=TD9s, min_offset=0, add_to=course)
TD11s = make_TD(TD_blocks, index=11, after=TD10s, min_offset=0, add_to=course)
TD12s = make_TD(TD_blocks, index=12, after=TD11s, min_offset=0, add_to=course)
TD13s = make_TD(TD_blocks, index=13, after=TD12s, min_offset=0, add_to=course)
CC2 = make_CC(index=2, after=TD13s, add_to=course)

path = f"activity_data/{course_label}.json"
with open(path, "w") as f:
    json.dump(course.to_dict(), f)
