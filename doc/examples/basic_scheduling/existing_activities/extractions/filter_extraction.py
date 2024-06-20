import pandas as pd
from automatic_university_scheduler.utils import read_from_yaml

path = "ade-export-polytech-2024-06-19-07-00-57.csv"
out_path = "raw_data.csv"
raw_data = pd.read_csv(path, header=0, index_col=None)
raw_data.fillna("", inplace=True)
tracked_ressources_path = "../../planification/preprocessing/tracked_ressources.yaml"
tracked_ressources = read_from_yaml(tracked_ressources_path)

for ind, row in raw_data.iterrows():
    # if row["Liste des salles"] == "Indéterminé":
    #     raw_data.drop(ind, inplace = True)
    teachers = row["_Bloc Liste Enseignants (étape 4)"]
    if not "AAAA" in teachers and not "BBBB" in teachers:
        raw_data.drop(ind, inplace=True)
raw_data.to_csv(out_path, index=False)
