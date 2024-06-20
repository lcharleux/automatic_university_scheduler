##############################################################################################################
# This script is used for extracting scheduling constraints from a given data file (either in .xlsx or .csv format).
# It first reads the data file and loads the setup information, student data, and tracked resources from their respective YAML files.
# Then, it calls the extract_constraints_from_table function to extract constraints and ignored resources from the raw data.
# Finally, it saves the extracted constraints and ignored resources to YAML files in a specified directory.
# The script is part of the automatic_university_scheduler package and is used for preprocessing data for university scheduling.
##############################################################################################################

import pandas as pd
import numpy as np
from automatic_university_scheduler.datetime import DateTime
from automatic_university_scheduler.scheduling import load_setup
from automatic_university_scheduler.utils import (
    dump_to_yaml,
    read_from_yaml,
    create_directory,
)

from automatic_university_scheduler.extraction import extract_constraints_from_table

# path = "ade-export-polytech-2024-06-19-07-00-57.xlsx"
path = "ade-export-polytech-2024-06-19-07-00-57.csv"
extracted_data_dir = "../planification/outputs/extracted_data/"
setup_path = "../setup.yaml"
tracked_ressources_path = "../planification/preprocessing/tracked_ressources.yaml"
student_data_path = "../student_data.yaml"

if path.endswith(".xlsx"):
    raw_data = pd.read_excel(f"extractions/{path}", header=0)
elif path.endswith(".csv"):
    raw_data = pd.read_csv(f"extractions/{path}", header=0)
else:
    raise ValueError("Invalid file format")
create_directory(extracted_data_dir)
setup = load_setup(setup_path)
student_data = read_from_yaml(student_data_path)
tracked_ressources = read_from_yaml(tracked_ressources_path)
constraints, ignored_ressources = extract_constraints_from_table(
    raw_data, setup, student_data, tracked_ressources
)
dump_to_yaml(constraints, f"{extracted_data_dir}/extracted_constraints.yaml")
dump_to_yaml(ignored_ressources, f"{extracted_data_dir}/ignored_ressources.yaml")
