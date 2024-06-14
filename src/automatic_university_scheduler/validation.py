import pandas as pd
from string import Template
import networkx as nx

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


class Colors:
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    OFF = "\033[0m"


class Messages:
    SUCCESS = f"{Colors.GREEN}SUCCESS{Colors.OFF}"
    WARNING = f"{Colors.YELLOW}WARNING{Colors.OFF}"
    ERROR = f"{Colors.RED}ERROR{Colors.OFF}"
    INFO = f"{Colors.BLUE}INFO{Colors.OFF}"
    CYCLE = f"{Colors.MAGENTA}CYCLE{Colors.OFF}"
    SOURCE = f"{Colors.CYAN}SOURCE{Colors.OFF}"
    SINK = f"{Colors.CYAN}SINK{Colors.OFF}"


def constraints_to_mermaid_graph(constraints: list) -> str:
    """
    Converts YAML constraint model to Mermaid graph.
    """
    text_constraints = ""
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
    text_constraints = Template(_mermaid_flow_template).substitute(
        GRAPH=text_constraints, TITLE="Constraints Graph"
    )
    return text_constraints


def activities_to_dataframe(activities: dict) -> pd.DataFrame:
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


def constraints_to_digraph(constraints: list) -> nx.DiGraph:
    """
    Converts YAML constraints to NetworkX DiGraph.
    """
    G = nx.DiGraph()
    for constraint in constraints:
        if constraint["kind"] == "succession":
            for start in constraint["start_after"]:
                for end in constraint["activities"]:
                    G.add_edge(start, end)
    return G


def graph_degrees(G: nx.DiGraph) -> pd.DataFrame:
    """
    Computes in and out degrees of a NetworkX DiGraph.
    """
    graph = pd.concat(
        [
            pd.Series(dict(G.in_degree(G.nodes)), name="in_degree"),
            pd.Series(dict(G.out_degree(G.nodes)), name="out_degree"),
        ],
        axis=1,
    )
    graph.index.name = "node"
    return graph


def cycles_in_graph(G: nx.DiGraph) -> list:
    """
    Detects cycles in a NetworkX DiGraph.
    """
    cycles = list(nx.simple_cycles(G))
    return cycles


def analyze_contraints_graph(constraints: list) -> pd.DataFrame:
    """
    Analyzes a YAML constraints graph.
    """
    G = constraints_to_digraph(constraints)

    # CYCLES DETECTION
    cycles = cycles_in_graph(G)
    if len(cycles) > 0:
        for cycle in cycles:
            print(f"    CYCLES: cycle detected in graph: {cycle} => {Messages.ERROR}")
            raise ValueError("Cycles detected in constraints graph")
    else:
        print(f"    CYCLES: success: no cycles detected in graph => {Messages.SUCCESS}")

    # GRAPH ANALYSIS
    graph_degrees_df = graph_degrees(G)
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
