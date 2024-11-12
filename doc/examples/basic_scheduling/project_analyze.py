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
import email
from email import generator
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication


setup = yaml.safe_load(open("setup.yaml"))
output_dir = setup["output_dir"]
create_directory(output_dir)
graph_output_dir = f"{output_dir}/validation/graphs/"
create_directory(graph_output_dir)
activities_output_dir = f"{output_dir}/validation/activities/"
create_directory(activities_output_dir)
emails_output_dir = f"{output_dir}/validation/emails/"
create_directory(emails_output_dir)

engine = create_engine(setup["engine"], echo=False)
Base.metadata.create_all(engine)
session = Session(engine)
project = session.execute(select(Project)).scalars().first()
deadline = "15/11/2024"

reminder_deadline = setup.get("reminder_deadline", "-PT24H")

for course in project.courses:
    G = course.activity_graph
    print(f"Course: {course.label}")
    graph_degrees_df, cycles = analyze_contraints_graph(G)
    html_graph_path = f"{graph_output_dir}/course_{course.label}_graph.html"
    graph_to_mermaid(
        G,
        path=html_graph_path,
        title=f"Course {course.label} Constraints Graph",
        format="html",
    )
    png_graph_path = f"{graph_output_dir}/course_{course.label}_graph.png"
    graph_to_mermaid(
        G,
        path=png_graph_path,
        title=f"Course {course.label} Constraints Graph",
        format="png",
    )

    activities = course.activities
    activities_df = activities_ressources_dataframe(project, activities)
    with open(
        f"{activities_output_dir}/course_{course.label}_activities.html", "w"
    ) as f:
        f.write(activities_df.to_html(index=False))

    to_address = course.manager.email

    from_address = course.planner.email
    msg = MIMEMultipart("related")
    msg["To"] = to_address
    msg["From"] = from_address
    msg["Subject"] = (
        "[Planification automatique] Validation modèle du module " + course.label
    )
    msg["Importance"] = "high"

    # Create the alternative part
    msg_alternative = MIMEMultipart("alternative")
    msg.attach(msg_alternative)

    # HTML body
    with open(
        f"{activities_output_dir}/course_{course.label}_activities.html", "r"
    ) as f:
        html_table = f.read()

    html_body = f"""
    <html>
    <body>
        <p>Bonjour {course.manager.full_name},</p>
        <p>Voilà la manière dont je compte planifier ton module. Tu trouveras ci-dessous deux types d'informations.</p>
        <p>1. Voici le tableau des activités planifiées: il fait le bilan des ressources que je vais utiliser pour chacune de ses activités.</p>
        {html_table}
        <p>2. Voici le graphique des contraintes: il indique les contraintes d'enchainement entre les différents groupes d'activités de ton module.</p>
        <img src="cid:course_graph">
        <p>J'attends de toi que je me dise si tu vois des erreurs dans les informations qui sont fournies ci-dessus par réponse à ce message avant le <b><span style="color:red;">{deadline}</span></b>. Sans réponse de ta part, je considère que tu valides mon modèle.</p>
        <p>Je reste à ta disposition pour toute question.</p>
        <p>En te souhaitant une radieuse journée.</p>
        <p>{course.planner.full_name}</p>
    </body>
    </html>
    """
    msg_alternative.attach(MIMEText(html_body, "html"))

    # Embed the PNG image
    with open(png_graph_path, "rb") as img_file:
        img = MIMEImage(img_file.read())
        img.add_header("Content-ID", "<course_graph>")
        img.add_header(
            "Content-Disposition", "inline", filename=f"course_{course.label}_graph.png"
        )
        msg.attach(img)

    # Create the reminder object
    reminder_body = f"""
    BEGIN:VCALENDAR
    VERSION:2.0
    BEGIN:VEVENT
    SUMMARY:Reminder
    DTSTART:{deadline.replace("/", "")}T090000Z
    BEGIN:VALARM
    TRIGGER:{reminder_deadline}
    ACTION:DISPLAY
    DESCRIPTION:Reminder
    END:VALARM
    END:VEVENT
    END:VCALENDAR
    """
    reminder = MIMEApplication(reminder_body, "ics")
    reminder.add_header("Content-Disposition", "attachment", filename="reminder.ics")

    msg.attach(reminder)

    # Save the email to a file
    mname = course.manager.full_name.replace(" ", "_")
    with open(f"{emails_output_dir}/message_{course.label}_{mname}.eml", "w") as f:
        emlGenerator = generator.Generator(f)
        emlGenerator.flatten(msg)
