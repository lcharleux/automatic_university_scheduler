import json
import copy

# MATH501


from automatic_university_scheduler.scheduling import Activity, Course

n_TD = 14
course_label = "EASI501"
course = Course(label=course_label, color="blue")
TD_blocks = [
    ("TDA", "Teacher_Lau"),
    ("TDB", "Teacher_YY"),
    ("TDC", "Teacher_Seb"),
    ("TDD", "Teacher_Lau"),
    ("TDE", "Teacher_Lau"),
    ("TDG", "Teacher_YY"),
]
TP_blocks = [
    ("TPA1", "Teacher_FLep"),
    ("TPA2", "Teacher_FLep"),
    ("TPB1", "Teacher_CHern"),
    ("TPB2", "Teacher_LMarech"),
    ("TPC1", "Teacher_CHern"),
    ("TPC2", "Teacher_MPass"),
    ("TPD1", "Teacher_FLep"),
    ("TPD2", "Teacher_MPass"),
    ("TPE1", "Teacher_MPass"),
    ("TPE2", "Teacher_FLep"),
    ("TPG1", "Teacher_FLep"),
    ("TPG2", "Teacher_FLep"),
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
    teachers=["Teacher_Flep"],
    rooms=["Room_amphi_1", "Room_amphi_2"],
):
    students = "CM_TC"
    label = f"{course_label}_{students}_CC{index}"
    activity = Activity(label=label, students="CM_TC", kind="EX")
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
    teachers=["Teacher_FLep"],
    rooms=["Room_amphi_1", "Room_amphi_2"],
):
    students = "CM_TC"
    label = f"{course_label}_{students}_CM{index}"
    activity = Activity(label=label, students="CM_TC", kind="CM", duration=6)
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
            label=f"{course_label}_{students}_TD{index}", students=students, duration=6
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
            duration=16,
        )
        if index == 1:
            TP_rooms = ["C121"]
        else:
            TP_rooms = ["A202"]

        activity.add_ressources(kind="teachers", quantity=1, pool=[teacher])
        activity.add_ressources(kind="rooms", quantity=1, pool=TP_rooms)
        if after != None:
            for other in after:
                activity.add_after(other, min_offset=min_offset)
        course.add_activity(activity)
        if add_to != None:
            add_to.add_activity(activity)
        activities.append(activity)
    return activities


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
# CM8 = make_CM(index=8, after=TD5s, add_to=course)


# CM9 = make_CM(index=9, after=TD6s, add_to=course)
CC1 = make_CC(index=1, after=TD5s, add_to=course)

TD6s = make_TD(TD_blocks, index=6, after=[CC1], min_offset=0, add_to=course)
TD7s = make_TD(TD_blocks, index=7, after=TD6s, min_offset=0, add_to=course)

TP1s = make_TP(TP_blocks, index=1, after=TD3s, min_offset=0, add_to=course)
TP2s = make_TP(TP_blocks, index=2, after=TP1s, min_offset=0, add_to=course)
TP3s = make_TP(TP_blocks, index=3, after=TP2s, min_offset=0, add_to=course)

CC2 = make_CC(index=2, after=TD6s + TP3s, add_to=course)

path = f"../activity_data/{course_label}.json"
with open(path, "w") as f:
    json.dump(course.to_dict(), f)
