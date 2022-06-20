import json
import copy

# MECA551


from scheduling import Activity, Course

n_TD = 14
course_label = "MECA551"
course = Course(label=course_label, color="magenta")
TD_blocks = [
    ("TDA", "Teacher_HFav"),
    ("TDB", "Teacher_HFav"),
    ("TDC", "Teacher_HFav"),
]
TP_blocks = [
    ("TDA1", "Teacher_HFav"),
    ("TDA2", "Teacher_TAve"),
    ("TDB1", "Teacher_HFav"),
    ("TDB2", "Teacher_TAve"),
    ("TDC1", "Teacher_Ater512"),
    ("TDC2", "Teacher_TAve"),
]
TD_rooms = ["C213", "C214", "C215"]
TD_rooms = ["C213", "C214", "C215", "C216", "C217"]
last_act = None
students = "CM_MM"


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


def make_TP(TP_blocks, index=1, after=None, min_offset=0, add_to=None):
    activities = []
    for students, teacher in TP_blocks:
        activity = Activity(
            label=f"{course_label}_{students}_TP{index}",
            students=students,
            kind="TP",
            duration=3,
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


TD1s = make_TD(TD_blocks, index=1, after=None, min_offset=0, add_to=course)
TD2s = make_TD(TD_blocks, index=2, after=TD1s, min_offset=0, add_to=course)
TD3s = make_TD(TD_blocks, index=3, after=TD2s, min_offset=0, add_to=course)
TP1s = make_TP(TD_blocks, index=1, after=TD2s, min_offset=0, add_to=course)
TP2s = make_TP(TD_blocks, index=2, after=TP1s, min_offset=0, add_to=course)
TP3s = make_TP(TD_blocks, index=3, after=TP2s, min_offset=0, add_to=course)
TP4s = make_TP(TD_blocks, index=4, after=TP3s, min_offset=0, add_to=course)
TP5s = make_TP(TD_blocks, index=5, after=TP4s, min_offset=0, add_to=course)
TP6s = make_TP(TD_blocks, index=6, after=TP5s, min_offset=0, add_to=course)
TP7s = make_TP(TD_blocks, index=7, after=TP6s, min_offset=0, add_to=course)
TP8s = make_TP(TD_blocks, index=8, after=TP7s, min_offset=0, add_to=course)
TP9s = make_TP(TD_blocks, index=9, after=TP8s, min_offset=0, add_to=course)

"""
TD4s = make_TD(TD_blocks, index=4, after=[CM6], min_offset=0, add_to=course)
CM7 = make_CM(index=7, after=TD4s, add_to=course)

TD5s = make_TD(TD_blocks, index=5, after=[CM7], min_offset=0, add_to=course)
CM8 = make_CM(index=8, after=TD5s, add_to=course)
TD6s = make_TD(TD_blocks, index=6, after=[CM8], min_offset=0, add_to=course)

CM9 = make_CM(index=9, after=TD6s, add_to=course)
CC1 = make_CC(index=1, after=[CM9], add_to=course)

TD7s = make_TD(TD_blocks, index=7, after=[CC1], min_offset=0, add_to=course)
v
TP2s = make_TP(TD_blocks, index=2, after=TP1s, min_offset=0, add_to=course)
TP3s = make_TP(TD_blocks, index=3, after=TP2s, min_offset=0, add_to=course)
TP4s = make_TP(TD_blocks, index=4, after=TP3s, min_offset=0, add_to=course)

CC2 = make_CC(index=2, after=TD6s + TP4s, add_to=course)
"""
path = f"activity_data/{course_label}.json"
with open(path, "w") as f:
    json.dump(course.to_dict(), f)
