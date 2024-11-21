import pandas as pd
from string import Template
import networkx as nx
from automatic_university_scheduler.utils import Messages, Colors
from mermaid.graph import Graph
from mermaid import Mermaid

_mermaid_flow_template_html = r"""
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

_mermaid_flow_template_png = r"""
    flowchart TB
    $GRAPH
"""

# def quarter_to_redeable(quarter):
#     """
#     Converts quarter of hour to human readable format.
#     output format is "x d: x h: x min".
#     """
#     sgn = 1
#     if quarter < 0:
#         sgn = -1
#         quarter = -quarter

#     days = quarter // 96
#     hours = (quarter % 96) // 4
#     minutes = (quarter % 96) % 4 * 15
#     if sgn == -1:
#         res = "-"
#     else:
#         res = ""

#     if days > 0:
#         res += f"{days}d"
#     if hours > 0:
#         res += f" {hours}h"
#     if minutes > 0:
#         res += f" {minutes}min"
#     return res


def graph_to_mermaid(graph, path, title="Constraints Graph", format="html") -> str:

    """
    Converts YAML constraint model to Mermaid graph.
    """
    text_constraints = ""
    for node in graph.nodes:
        if '-s' in node:
            text_constraints += f"        {node}[/{node}\]:::SPclass\n"
        elif '-e' in node:
            text_constraints += f"        {node}[\{node}/]:::SPclass\n"
        elif 'CM' in node:
            text_constraints += f"        {node}:::CMclass\n"
        elif 'TD' in node:
            text_constraints += f"        {node}:::TDclass\n"
        elif 'TP' in node:
            text_constraints += f"        {node}:::TPclass\n"
        elif ('CT' in node) or ('CI' in node) or ('ET' in node) or('CC' in node):
            text_constraints += f"        {node}:::EXclass\n"
        else:
            text_constraints += f"        {node}\n"
    text_constraints += "        classDef SPclass fill:#c5d4c5, stroke: #c5d4c5, color:#fff\n"
    text_constraints += "        classDef CMclass fill:#f96\n"
    text_constraints += "        classDef TDclass fill:#f69\n"
    text_constraints += "        classDef TPclass fill:#69f\n"
    text_constraints += "        classDef EXclass fill:#6f9\n"
    for edge in graph.edges:
        start, end = edge
        edata = graph.edges[edge]
        offset = None
        min_offset = edata["min_offset"]
        max_offset = edata["max_offset"]
        if min_offset is not None or max_offset is not None:
            offset = ""
            if min_offset is not None:
                offset += f"{min_offset} <= \u0394t"
            else:
                min_offset = "*"
                offset += f"{min_offset} <= \u0394t"
            if max_offset is not None:
                offset += f" <= {max_offset}"

        text_constraints += f"        {start} -->|{offset}| {end}\n"
    
    text_constraints = text_constraints.strip()
    if format == "html":
        text_constraints = Template(_mermaid_flow_template_html).substitute(
            GRAPH=text_constraints, TITLE=title
        )
        with open(path, "w") as f:
            f.write(text_constraints)
    if format == "png":
        text_constraints = Template(_mermaid_flow_template_png).substitute(
            GRAPH=text_constraints, TITLE=title
        )
        graph = Graph(title="simple graph", script=text_constraints)
        render = Mermaid(graph)
        render.to_png(path)

    return text_constraints


def analyze_contraints_graph(graph) -> pd.DataFrame:
    """
    Analyzes a YAML constraints graph.
    """

    # CYCLES DETECTION
    cycles = cycles_in_graph(graph)
    if len(cycles) > 0:
        for cycle in cycles:
            print(f"    CYCLES: cycle detected in graph: {cycle} => {Messages.ERROR}")
            # raise ValueError("Cycles detected in constraints graph")
    else:
        print(f"    CYCLES: success: no cycles detected in graph => {Messages.SUCCESS}")

    # GRAPH ANALYSIS
    graph_degrees_df = graph_degrees(graph)
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
            f"    SINK NODES: {sink_nodes[0]} is the only sink node => {Messages.SUCCESS}"
        )
    else:
        print(
            f"    SINK NODES: {len(sink_nodes)} sink nodes detected: {sink_nodes} => {Messages.WARNING}"
        )
    return graph_degrees_df, cycles


def activities_ressources_dataframe(project, activities: dict) -> pd.DataFrame:
    """
    Summarizes YAML activities as a Pandas DataFrame.
    """
    out = []
    for activity in activities:
        out.append(activity.ressources_to_series)
    out = pd.concat(out, axis=1).transpose()
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


# def analyze_contraints_graph(constraints: list) -> pd.DataFrame:
#     """
#     Analyzes a YAML constraints graph.
#     """
#     G = constraints_to_digraph(constraints)

#     # CYCLES DETECTION
#     cycles = cycles_in_graph(G)
#     if len(cycles) > 0:
#         for cycle in cycles:
#             print(f"    CYCLES: cycle detected in graph: {cycle} => {Messages.ERROR}")
#             raise ValueError("Cycles detected in constraints graph")
#     else:
#         print(f"    CYCLES: success: no cycles detected in graph => {Messages.SUCCESS}")

#     # GRAPH ANALYSIS
#     graph_degrees_df = graph_degrees(G)
#     source_nodes = list(graph_degrees_df[graph_degrees_df.in_degree == 0].index)
#     sink_nodes = list(graph_degrees_df[graph_degrees_df.out_degree == 0].index)
#     if len(source_nodes) == 1:
#         print(
#             f"    SOURCE NODES: {source_nodes[0]} is the only source node => {Messages.SUCCESS}"
#         )
#     else:
#         print(
#             f"    SOURCE NODES: {len(source_nodes)} source nodes detected: {source_nodes} => {Messages.WARNING}"
#         )
#     if len(sink_nodes) == 1:
#         print(
#             f"    SINK NODES: {sink_nodes[0]} is the only sink node = {Messages.SUCCESS}"
#         )
#     else:
#         print(
#             f"    SINK NODES: {len(sink_nodes)} sink nodes detected: {sink_nodes} => {Messages.WARNING}"
#         )
#     return graph_degrees_df, cycles
