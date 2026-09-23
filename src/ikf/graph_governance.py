"""Pure graph-governance helpers for IKF views and validation.

The helpers distinguish evidence scope from visual filtering and explicitly keep
chronology separate from causality.
"""

from __future__ import annotations


CHRONOLOGY_RELATIONSHIPS = {"FOLLOWED_BY"}
CAUSAL_RELATIONSHIPS = {"CAUSED", "CAUSED_BY", "CONTRIBUTED_TO", "LED_TO"}
STRUCTURAL_RELATIONSHIPS = {
    "INVOLVED_IN",
    "HAS_SOURCE",
    "HAS_MODEL_RUN",
    "HAS_QUESTION_RUN",
    "HAS_MODEL_ANSWER",
    "HAS_REVIEW",
}


def relationship_semantics(relationship: str) -> str:
    value = str(relationship or "").strip().upper()
    if value in CHRONOLOGY_RELATIONSHIPS:
        return "CHRONOLOGY"
    if value in CAUSAL_RELATIONSHIPS:
        return "CAUSAL_OR_CONTRIBUTORY"
    if value in STRUCTURAL_RELATIONSHIPS:
        return "STRUCTURAL"
    return "SEMANTIC"


def is_causal_relationship(relationship: str) -> bool:
    return relationship_semantics(relationship) == "CAUSAL_OR_CONTRIBUTORY"


def evidence_intersects_scope(evidence_document_ids, selected_document_ids) -> bool:
    selected = {str(v) for v in selected_document_ids or [] if v}
    evidence = {str(v) for v in evidence_document_ids or [] if v}
    if not selected:
        return True
    return bool(evidence & selected)


def evidence_backed_node_ids(nodes, selected_document_ids):
    """Return node IDs supported by the selected evidence-document scope."""
    retained = set()
    for node in nodes or []:
        node_id = node.get("node_id")
        if not node_id:
            continue
        if evidence_intersects_scope(
            node.get("evidence_document_ids"),
            selected_document_ids,
        ):
            retained.add(node_id)
    return retained


def add_structural_passthrough_nodes(*, retained_node_ids, edges):
    """Add only structural one-hop connectors touching retained evidence nodes.

    This supports a readable graph without allowing structural plumbing to pull
    unrelated semantic content into a document-scoped view.
    """
    retained = set(retained_node_ids or [])
    changed = True
    while changed:
        changed = False
        for edge in edges or []:
            if relationship_semantics(edge.get("relationship")) != "STRUCTURAL":
                continue
            source = edge.get("source_node_id")
            target = edge.get("target_node_id")
            if source in retained and target and target not in retained:
                retained.add(target)
                changed = True
            elif target in retained and source and source not in retained:
                retained.add(source)
                changed = True
    return retained


def filter_edges_for_nodes(edges, retained_node_ids):
    retained = set(retained_node_ids or [])
    return [
        edge
        for edge in (edges or [])
        if edge.get("source_node_id") in retained
        and edge.get("target_node_id") in retained
    ]
