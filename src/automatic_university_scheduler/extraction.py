import pandas as pd
import numpy as np
from automatic_university_scheduler.datetime import DateTime


def extract_constraints_from_table(
    raw_data, setup, student_data, tracked_ressources, format="USMB"
):
    """
    Extracts constraints from a given table of raw data based on the setup, student data, and tracked resources.

    The constraints are based on the availability of teachers, rooms, and students. The function also handles different formats of raw data, with "USMB" as the default format.

    Parameters:
    raw_data (DataFrame): The raw data from which to extract constraints.
    setup (dict): A dictionary containing setup information such as week structure, origin datetime, horizon, time slot duration, max weeks, time slots per week, activities kinds, days per week, and time slots per day.
    student_data (dict): A dictionary containing student data.
    tracked_ressources (dict): A dictionary containing tracked resources.
    format (str, optional): The format of the raw data. Defaults to "USMB".

    Returns:
    tuple: A tuple containing two dictionaries. The first dictionary contains the extracted constraints. The second dictionary contains the ignored resources.
    """
    WEEK_STRUCTURE = setup["WEEK_STRUCTURE"]
    ORIGIN_DATETIME = setup["ORIGIN_DATETIME"]
    HORIZON = setup["HORIZON"]
    TIME_SLOT_DURATION = setup["TIME_SLOT_DURATION"]
    MAX_WEEKS = setup["MAX_WEEKS"]
    TIME_SLOTS_PER_WEEK = setup["TIME_SLOTS_PER_WEEK"]
    activities_kinds = setup["ACTIVITIES_KINDS"]
    DAYS_PER_WEEK = setup["DAYS_PER_WEEK"]
    TIME_SLOTS_PER_DAY = setup["TIME_SLOTS_PER_DAY"]

    if format == "USMB":
        slot_string_key = 'Chaîne qui référenence les créneaux occupés par tranche de 15mn de "00:00" à "23:45". (de gauche à droite car n°1 = plage de 00:00 à 00:15 -> car n°96 = plage de 23:45 à 00:00)'
        raw_data = raw_data[raw_data["Année"].isna() == False]  # REMOVE LAST EMPTY LINE

        def process_weekday(s):
            weekday_map = {
                "lundi": 1,
                "mardi": 2,
                "mercredi": 3,
                "jeudi": 4,
                "vendredi": 5,
                "samedi": 6,
                "dimanche": 7,
            }
            return weekday_map[s]

        def process_students_and_teachers(s):
            if type(s) == float:
                return ""
            else:
                return s

        col_map = {
            "year": lambda df: df["Année"].values.astype(np.int32),
            "week": lambda df: df["Semaine"].values.astype(np.int32),
            "weekday": lambda df: df["Jour"].map(process_weekday),
            "from_dayslot": lambda df: df[slot_string_key].map(lambda s: s.index("1")),
            "to_dayslot": lambda df: df[slot_string_key].map(
                lambda s: TIME_SLOTS_PER_DAY - s[::-1].index("1")
            ),
            "rooms": lambda df: df["Liste des salles"].map(
                lambda s: s.replace("Indéterminé", "")
            ),
            "students": lambda df: df["Nom des groupes étudiants"].map(
                process_students_and_teachers
            ),
            "teachers": lambda df: df["_Bloc Liste Enseignants (étape 4)"].map(
                process_students_and_teachers
            ),
            "school": lambda df: df["Composantes groupes étudiants"].map(
                lambda s: s.replace("Indéterminé", "")
            ),
        }

        data = {}
        for k, f in col_map.items():
            data[k] = f(raw_data)
        data = pd.DataFrame(data)

        constraints = {}
        ignored_ressources = {"teachers": [], "rooms": [], "students": []}
        for kind in ["teachers", "rooms"]:
            constraints[kind] = {
                r: {"unavailable": []} for r in tracked_ressources[kind]
            }
        constraints["students"] = {
            r: {"unavailable": []} for r in student_data["groups"].keys() if r != None
        }

        for index, row in data.iterrows():
            start_time = TIME_SLOT_DURATION * row["from_dayslot"]
            start_time_seconds = start_time.total_seconds()
            start_time_hours = int(start_time_seconds // 3600)
            start_time_minutes = int(
                (start_time_seconds - start_time_hours * 3600) // 60
            )
            start_str = f"{row['year']}-W{ str(row['week']).zfill(2)}-{row['weekday']} {str(start_time_hours).zfill(2) }:{str(start_time_minutes).zfill(2)}"
            start_datetime = DateTime.from_str(start_str)
            end_time = TIME_SLOT_DURATION * row["to_dayslot"]
            end_time_seconds = end_time.total_seconds()
            end_time_hours = int(end_time_seconds // 3600)
            end_time_minutes = int((end_time_seconds - end_time_hours * 3600) // 60)
            end_str = f"{row['year']}-W{ str(row['week']).zfill(2)}-{row['weekday']} {str(end_time_hours).zfill(2) }:{str(end_time_minutes).zfill(2)}"
            end_datetime = DateTime.from_str(end_str)
            constraint = {
                "kind": "datetime",
                "start": start_datetime.to_str(),
                "end": end_datetime.to_str(),
            }
            for kind in ["teachers", "students", "rooms"]:
                if row[kind] != "":
                    ressources = [r.strip() for r in row[kind].split(",")]
                    for ressource in ressources:
                        if ressource in constraints[kind].keys():
                            constraints[kind][ressource]["unavailable"].append(
                                constraint
                            )
                        else:
                            ignored_ressources[kind].append(ressource)

        for kind in ["teachers", "rooms", "students"]:
            ignored_ressources[kind] = sorted(list(set(ignored_ressources[kind])))

        return constraints, ignored_ressources
