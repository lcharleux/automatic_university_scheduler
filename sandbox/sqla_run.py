from classes import Base, Room, Activity, StudentsGroup, AtomicStudent
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
import yaml

setup = yaml.safe_load(open("setup.yaml"))


engine = create_engine(setup["engine"], echo=False)
Base.metadata.create_all(engine)


session = Session(engine)


activities = session.execute(select(Activity)).scalars().all()
print("Activities:")
for activity in activities:
    print(activity)

act1 = activities[0]


students_groups = session.execute(select(StudentsGroup)).scalars().all()

atomic_students = session.execute(select(AtomicStudent)).scalars().all()
