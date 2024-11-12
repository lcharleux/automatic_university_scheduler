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
activities_output_dir = f"{output_dir}/planification/activities/"
create_directory(activities_output_dir)


engine = create_engine(setup["engine"], echo=False)
Base.metadata.create_all(engine)
session = Session(engine)
project = session.execute(select(Project)).scalars().first()

writer = pd.ExcelWriter(
    f"{activities_output_dir}/scheduled_activities.xlsx", engine="xlsxwriter"
)

for course in project.courses:
    label = course.label
    sheet_name = f"{label}"
    # DATA TO EXCEL
    out = []

    for activity in course.activities:
        out.append(activity.planification_to_series)
    out = pd.concat(out, axis=1).transpose()
    out.to_excel(writer, sheet_name=sheet_name, index=False, startrow=0)

    worksheet = writer.sheets[sheet_name]
    workbook = writer.book
    my_format = workbook.add_format(
        {"align": "center", "valign": "vcenter", "border": 0, "font_size": 11}
    )
    worksheet.set_column("A:I", 10, my_format)
    worksheet.set_column("H:H", 20, my_format)
    worksheet.set_column("J:L", 30, my_format)

    tag = f"A1:I1"
    worksheet.autofilter(tag)

writer.close()
