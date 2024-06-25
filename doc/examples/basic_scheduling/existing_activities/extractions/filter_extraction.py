import pandas as pd
from automatic_university_scheduler.utils import read_from_yaml

path = "ade-export-polytech-2024-06-19-07-00-57.csv"
out_path = "filtered_data.csv"
raw_data = pd.read_csv(path, header=0, index_col=None)
raw_data = raw_data.fillna("")
tracked_ressources_path = "../../planification/preprocessing/tracked_ressources.yaml"
tracked_ressources = read_from_yaml(tracked_ressources_path)

out = []
for ind, row in raw_data.iterrows():
    # if row["Liste des salles"] == "Indéterminé":
    #     raw_data.drop(ind, inplace = True)
    teachers = row["_Bloc Liste Enseignants (étape 4)"]
    if "AAAA" in teachers or "BBBB" in teachers:
        # raw_data.drop(ind, inplace=True)
        out.append(row)
out_data = pd.DataFrame(out)
out_data.to_csv(out_path, index=False)
