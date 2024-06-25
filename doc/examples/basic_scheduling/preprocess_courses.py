from automatic_university_scheduler.validation import (
    constraints_to_mermaid_graph,
    activities_to_dataframe,
    analyze_contraints_graph,
)
from automatic_university_scheduler.preprocessing import (
    create_course_activities,
    get_unique_ressources_in_activities,
    get_unique_students_in_activities,
)
from automatic_university_scheduler.utils import create_directories
from automatic_university_scheduler.scheduling import load_setup, read_json_data
from automatic_university_scheduler.utils import dump_to_yaml, read_from_yaml
import yaml
import pandas as pd
import json
import os
import networkx as nx
import matplotlib.pyplot as plt
import numpy as np

# SETUP
setup = load_setup("setup.yaml")
WEEK_STRUCTURE = setup["WEEK_STRUCTURE"]
ORIGIN_DATETIME = setup["ORIGIN_DATETIME"]
HORIZON = setup["HORIZON"]
TIME_SLOT_DURATION = setup["TIME_SLOT_DURATION"]
MAX_WEEKS = setup["MAX_WEEKS"]


# DATA
room_data = read_from_yaml("room_data.yaml")
default_rooms = room_data["default_rooms"]
room_pools = room_data["room_pools"]
teacher_data = read_from_yaml("teacher_data.yaml")
teacher_full_names = {key: value["full_name"] for key, value in teacher_data.items()}
student_data = read_from_yaml("student_data.yaml")

# DIRECTORIES
course_models_dir = "course_models"
planification_dir = "planification/preprocessing"
course_graphs_dir = f"{planification_dir}/courses_graphs"
course_dataframes_dir = f"{planification_dir}/courses_activities_dataframes"
activities_dir = f"{planification_dir}/activities"
course_graph_analysis_dir = f"{planification_dir}/courses_graph_analysis"

create_directories(
    [
        course_graphs_dir,
        course_dataframes_dir,
        planification_dir,
        activities_dir,
        course_graph_analysis_dir,
    ]
)


print("PRE-PROCESSING COURSES")
models = sorted([f for f in os.listdir(course_models_dir) if f.endswith(".yaml")])
for model in models:
    data = yaml.safe_load(open(f"{course_models_dir}/{model}"))
    for course_label, course_data in data.items():
        print(f"  > PRE-PROCESSING: {course_label}")

        # CONSTRAINTS GRAPH TO MERMAID
        constraints = course_data["constraints"]
        constraints_graph = constraints_to_mermaid_graph(constraints)
        open(f"{course_graphs_dir}/{course_label}_graph.html", "w").write(
            constraints_graph
        )

        # CONSTRAINT GRAPH TO NETWORKX
        constraints = course_data["constraints"]
        graph_degrees_df, cycles = analyze_contraints_graph(constraints)
        graph_degrees_df.to_csv(
            f"{course_graph_analysis_dir}/{course_label}_graph_degrees.csv"
        )

        # RESSOURCES VALIDATION
        activities = course_data["activities"]
        out_df = activities_to_dataframe(activities)
        out_df.to_csv(f"{course_dataframes_dir}/{course_label}_ressources.csv")
        out_df.to_html(f"{course_dataframes_dir}/{course_label}_ressources.html")

        # ACTIVITIES
        course = create_course_activities(
            course_label=course_label,
            course_data=course_data,
            room_pools=room_pools,
            default_rooms=default_rooms,
            teacher_full_names=teacher_full_names,
            origin_datetime=ORIGIN_DATETIME,
            slot_duration=TIME_SLOT_DURATION,
        )

        path = f"{activities_dir}/{course_label}.json"
        with open(path, "w") as f:
            json.dump(course.to_dict(), f)

activity_data = read_json_data(activities_dir)
student_groups = np.array(list(student_data["groups"].keys()))
student_groups = student_groups[student_groups != None]
tracked_ressources = {
    "teachers": get_unique_ressources_in_activities(activity_data, kind="teachers"),
    "rooms": get_unique_ressources_in_activities(activity_data, kind="rooms"),
    "students": student_groups,
}
ressource_existing_intervals = {
    k: {t: [] for t in tracked_ressources[k]} for k in ["teachers", "rooms"]
}
dump_to_yaml(
    {k: v.tolist() for k, v in tracked_ressources.items()},
    f"{planification_dir}/tracked_ressources.yaml",
)
