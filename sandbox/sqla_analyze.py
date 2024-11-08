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
from sqlalchemy.exc import IntegrityError
import yaml
from ortools.sat.python import cp_model
import itertools
import numpy as np
from automatic_university_scheduler.datetimeutils import DateTime as DT
from automatic_university_scheduler.utils import Messages
from automatic_university_scheduler.optimize import SolutionPrinter
from automatic_university_scheduler.datetimeutils import slot_to_datetime
from automatic_university_scheduler.validation import cycles_in_graph, graph_degrees
import time
import pandas as pd
import networkx as nx
from string import Template

_mermaid_flow_template = r"""
<html lang="fr">
<head>
    <meta charset="utf-8" />
</head>
<body>
<h1>
$TITLE
</h1>
    <pre class="mermaid">
    flowchart TB
    $GRAPH
    </pre>
    <script type="module">
    import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@9/dist/mermaid.esm.min.mjs';
    mermaid.initialize({ startOnLoad: true });
    </script>
</body>
</html>
"""


def graph_to_mermaid(graph, title="Constraints Graph") -> str:

    """
    Converts YAML constraint model to Mermaid graph.
    """
    text_constraints = ""
    for edge in graph.edges:
        start, end = edge
        edata = graph.edges[edge]
        offset = None
        min_offset = edata["min_offset"]
        max_offset = edata["max_offset"]
        if min_offset != None or max_offset != None:
            offset = ""
            if min_offset != None:
                offset += f"{min_offset} <= t"
            else:
                min_offset = "*"
                offset += f"{min_offset} <= t"
            if max_offset != None:
                offset += f" <= {max_offset}"

        # for start in constraint["start_after"]:
        #     if "CM" in start:
        #         start += ":::CMclass"
        #     if "TD" in start:
        #         start += ":::TDclass"
        #     if "TP" in start:
        #         start += ":::TPclass"

        text_constraints += f"        {start} -->|{offset}| {end}\n"

    text_constraints = Template(_mermaid_flow_template).substitute(
        GRAPH=text_constraints, TITLE=title
    )

    return text_constraints


def analyze_contraints_graph(graph) -> pd.DataFrame:
    """
    Analyzes a YAML constraints graph.
    """

    # CYCLES DETECTION
    cycles = cycles_in_graph(graph)
    if len(cycles) > 0:
        for cycle in cycles:
            print(f"    CYCLES: cycle detected in graph: {cycle} => {Messages.ERROR}")
            raise ValueError("Cycles detected in constraints graph")
    else:
        print(f"    CYCLES: success: no cycles detected in graph => {Messages.SUCCESS}")

    # GRAPH ANALYSIS
    graph_degrees_df = graph_degrees(graph)
    source_nodes = list(graph_degrees_df[graph_degrees_df.in_degree == 0].index)
    sink_nodes = list(graph_degrees_df[graph_degrees_df.out_degree == 0].index)
    if len(source_nodes) == 1:
        print(
            f"    SOURCE NODES: {source_nodes[0]} is the only source node => {Messages.SUCCESS}"
        )
    else:
        print(
            f"    SOURCE NODES: {len(source_nodes)} source nodes detected: {source_nodes} => {Messages.WARNING}"
        )
    if len(sink_nodes) == 1:
        print(
            f"    SINK NODES: {sink_nodes[0]} is the only sink node = {Messages.SUCCESS}"
        )
    else:
        print(
            f"    SINK NODES: {len(sink_nodes)} sink nodes detected: {sink_nodes} => {Messages.WARNING}"
        )
    return graph_degrees_df, cycles


setup = yaml.safe_load(open("setup.yaml"))


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

# Graphs


for course in courses:
    G = nx.DiGraph()
    ag = course.activity_groups
    for group in ag:
        l = group.label
        G.add_node(l)
        for sa in group.starts_after:
            og = sa.to_activity_group
            ol = og.label
            G.add_edge(l, ol)
            min_offset_slots = sa.min_offset
            max_offset_slots = sa.max_offset
            min_offset = project.slots_to_duration(min_offset_slots)
            max_offset = project.slots_to_duration(max_offset_slots)
            G.edges[l, ol]["min_offset_slots"] = min_offset_slots
            G.edges[l, ol]["max_offset_slots"] = max_offset_slots
            G.edges[l, ol]["min_offset"] = min_offset
            G.edges[l, ol]["max_offset"] = max_offset

    print(f"Course: {course.label}")
    graph_degrees_df, cycles = analyze_contraints_graph(G)

    mermaid_graph = graph_to_mermaid(
        G, title=f"Course {course.label} Constraints Graph"
    )
    with open(f"course_{course.label}_graph.html", "w") as f:
        f.write(mermaid_graph)
