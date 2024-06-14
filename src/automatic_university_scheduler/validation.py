import pandas as pd
from string import Template

template = r"""
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

def quarter_to_redeable(quarter):
    """
    Converts quarter of hour to human readable format.
    output format is "x d: x h: x min".
    """
    days = quarter // 96
    hours = (quarter % 96) // 4
    minutes = (quarter % 96) % 4 * 15
    res= ""
    if days > 0:
        res += f"{days}d"
    if hours > 0:
        res += f" {hours}h"
    if minutes > 0:
        res += f" {minutes}min"
    return res


def constraints_to_graph(constraints):
    """
    Converts YAML constraint model to Mermaid graph.
    """
    #text_constraints = "::: mermaid\n    graph TB\n"
    text_constraints = ""
    for constraint in constraints:
        if constraint["kind"] == "succession":
            offset = ""
            if "min_offset" in constraint.keys():
                min_offset = constraint["min_offset"]
                if min_offset != None:
                    min_offset = quarter_to_redeable(min_offset)
                    offset += f"{min_offset} <= t"
                if min_offset == None:
                    min_offset = "0"
                    offset += f"{min_offset} <= t"
            if "max_offset" in constraint.keys():
                max_offset = constraint["max_offset"]
                if max_offset != None:
                    if len(offset) == 0:
                        offset += "t"
                    max_offset = quarter_to_redeable(max_offset)
                    offset += f" <= {max_offset}"
                if max_offset == None:
                    max_offset = "inf"
                    offset += f" <= {max_offset}"

            for start in constraint["start_after"]:
                if "CM" in start:
                    start += ":::CMclass"
                if "TD" in start:
                    start += ":::TDclass"
                if "TP" in start:
                    start += ":::TPclass"
                for end in constraint["activities"]:
                    text_constraints += f"        {start} -->|{offset}| {end}\n"

    text_constraints += "     classDef CMclass fill:#f77\n"
    text_constraints += "     classDef TDclass fill:#7f7\n"
    text_constraints += "     classDef TPclass fill:#77f\n"

    text_constraints = Template(template).substitute(GRAPH = text_constraints, TITLE = "Constrainte")

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
