from automatic_university_scheduler.database import (
    Base,
    Room,
    Activity,
    StudentsGroup,
    AtomicStudent,
    Project,
    Teacher,
    StartsAfterConstraint,
    ActivityGroup,
    ActivityKind,
    StaticActivity,
    Course,
)
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

import yaml
import numpy as np
from automatic_university_scheduler.validation import (
    analyze_contraints_graph,
    graph_to_mermaid,
    activities_ressources_dataframe,
)
from automatic_university_scheduler.utils import create_directory, create_directories
import time
import pandas as pd
import networkx as nx
from string import Template


setup = yaml.safe_load(open("setup.yaml"))
output_dir = setup["output_dir"]
create_directory(output_dir)
graph_output_dir = f"{output_dir}/validation/graphs/"
create_directory(graph_output_dir)
activities_output_dir = f"{output_dir}/validation/activities/"
create_directory(activities_output_dir)

engine = create_engine(setup["engine"], echo=False)
Base.metadata.create_all(engine)
session = Session(engine)
project = session.execute(select(Project)).scalars().first()
activities = session.execute(select(Activity)).scalars().all()
activity_groups = session.execute(select(ActivityGroup)).scalars().all()
courses = session.execute(select(Course)).scalars().all()
static_activities = session.execute(select(StaticActivity)).scalars().all()
students_groups = session.execute(select(StudentsGroup)).scalars().all()
atomic_students = session.execute(select(AtomicStudent)).scalars().all()
rooms = session.execute(select(Room)).scalars().all()
teachers = session.execute(select(Teacher)).scalars().all()
activity_kinds = session.execute(select(ActivityKind)).scalars().all()
starts_after_constraints = (
    session.execute(select(StartsAfterConstraint)).scalars().all()
)


for course in courses:
    G = course.activity_graph
    print(f"Course: {course.label}")
    graph_degrees_df, cycles = analyze_contraints_graph(G)
    mermaid_graph = graph_to_mermaid(
        G, title=f"Course {course.label} Constraints Graph"
    )
    with open(f"{graph_output_dir}/course_{course.label}_graph.html", "w") as f:
        f.write(mermaid_graph)

    activities = course.activities
    activities_df = activities_ressources_dataframe(project, activities)
    with open(
        f"{activities_output_dir}/course_{course.label}_activtities.html", "w"
    ) as f:
        f.write(activities_df.to_html(index=False))
