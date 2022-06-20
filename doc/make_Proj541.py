import json
import copy

# PROJ541


from scheduling import Activity, Course


info_rooms = ["Room_C213", "Room_C214", "Room_C215", "Room_C216", "Room_C217"]


def make_TP8h(
    index,
    students,
    rooms,
    after=None,
    add_to=None,
    min_offset=0,
    max_offset=None,
    teachers=["Math_Teacher_1"],
    room_quantity=1,
):
    label = f"{course_label}_G-{students}_TP-{index}"
    activity = Activity(kind="TP", label=label, students=students, duration=3)
    activity.add_ressources(kind="teachers", quantity=1, pool=teachers)
    activity.add_ressources(kind="rooms", quantity=room_quantity, pool=rooms)
    if after != None:
        for other in after:
            activity.add_after(other, min_offset=min_offset, max_offset=max_offset)

    if add_to != None:
        add_to.add_activity(activity)
    return activity


course_label = "Proj541"
course = Course(label=course_label, color="blue")


for students in ["TPD1", "TPD2", "TPE1", "TPE2"]:
    TP1 = make_TP8h(
        index=1,
        students=students,
        rooms=["A117"],
        add_to=course,
        min_offset=None,
        teachers=["Teacher_FV"],
    )
    TP2 = make_TP8h(
        index=2,
        students=students,
        rooms=["A117"],
        add_to=course,
        min_offset=1,
        max_offset=1,
        teachers=["Teacher_FV"],
        after=[TP1],
    )

    TP3 = make_TP8h(
        index=3,
        students=students,
        rooms=["B206"],
        add_to=course,
        min_offset=None,
        teachers=["Teacher_SM"],
    )
    TP4 = make_TP8h(
        index=4,
        students=students,
        rooms=["B206"],
        add_to=course,
        min_offset=1,
        max_offset=1,
        teachers=["Teacher_SM"],
        after=[TP3],
    )

    TP5 = make_TP8h(
        index=5,
        students=students,
        rooms=["C121"],
        add_to=course,
        min_offset=None,
        teachers=["Teacher_FL"],
    )
    TP6 = make_TP8h(
        index=6,
        students=students,
        rooms=["C121"],
        add_to=course,
        min_offset=1,
        max_offset=1,
        teachers=["Teacher_FL"],
        after=[TP5],
    )

    TP7 = make_TP8h(
        index=7,
        students=students,
        rooms=info_rooms,
        add_to=course,
        min_offset=None,
        teachers=["Teacher_ET"],
    )
    TP8 = make_TP8h(
        index=8,
        students=students,
        rooms=info_rooms,
        add_to=course,
        min_offset=1,
        max_offset=1,
        teachers=["Teacher_YY"],
        after=[TP7],
    )

    TP9 = make_TP8h(
        index=7,
        students=students,
        rooms=["C119", "C120"],
        room_quantity=2,
        add_to=course,
        min_offset=None,
        teachers=["Teacher_PM"],
    )
    TP10 = make_TP8h(
        index=8,
        students=students,
        rooms=["C119", "C120"],
        room_quantity=2,
        add_to=course,
        min_offset=1,
        max_offset=1,
        teachers=["Teacher_PM"],
        after=[TP9],
    )
path = f"activity_data/{course_label}.json"
with open(path, "w") as f:
    json.dump(course.to_dict(), f)
