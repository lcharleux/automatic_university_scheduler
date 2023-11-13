import pandas as pd


def constraints_to_graph(constraints):
    """
    Converts YAML constraint model to Mermaid graph.
    """
    text_constraints = "::: mermaid\n    graph TB\n"
    for constraint in constraints:
        if constraint["kind"] == "succession":
            offset = ""
            if "min_offset" in constraint.keys():
                min_offset = constraint["min_offset"]
                if min_offset != None:
                    offset += f"{min_offset} <= t"
            if "max_offset" in constraint.keys():
                max_offset = constraint["max_offset"]
                if max_offset != None:
                    if len(offset) == 0:
                        offset += "t"
                    offset += f" <= {max_offset}"

            for start in constraint["start_after"]:
                for end in constraint["activities"]:
                    text_constraints += f"        {start} -->|{offset}| {end}\n"
    text_constraints += ":::"
    return text_constraints


def activities_to_dataframe(activities):
    """
    Summarizes YAML activities as a Pandas DataFrame.
    """
    out = {
        "kind": [],
        "duration": [],
        "students": [],
        "teachers": [],
        "Nteachers": [],
        "rooms": [],
        "Nrooms": [],
    }
    index = []
    for label, activity in activities.items():
        index.append(label)
        out["kind"].append(activity["kind"])
        out["duration"].append(activity["duration"])
        out["students"].append(activity["students"])
        out["teachers"].append(str(activity["teachers"]["pool"]))
        out["Nteachers"].append(activity["teachers"]["value"])
        out["rooms"].append(str(activity["rooms"]["pool"]))
        out["Nrooms"].append(activity["rooms"]["value"])
    out = pd.DataFrame(out, index=index)
    out.index.name = "label"
    return out
