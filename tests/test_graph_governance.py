from ikf.graph_governance import (
    add_structural_passthrough_nodes,
    evidence_backed_node_ids,
    filter_edges_for_nodes,
    is_causal_relationship,
    relationship_semantics,
)


def test_followed_by_is_chronology_not_causality():
    assert relationship_semantics("FOLLOWED_BY") == "CHRONOLOGY"
    assert not is_causal_relationship("FOLLOWED_BY")
    assert is_causal_relationship("CONTRIBUTED_TO")


def test_document_scope_keeps_only_evidence_backed_nodes():
    nodes = [
        {"node_id": "n1", "evidence_document_ids": ["d1"]},
        {"node_id": "n2", "evidence_document_ids": ["d2"]},
        {"node_id": "n3", "evidence_document_ids": ["d1", "d2"]},
    ]
    assert evidence_backed_node_ids(nodes, ["d1"]) == {"n1", "n3"}


def test_structural_passthrough_can_preserve_connector_only():
    edges = [
        {
            "source_node_id": "n1",
            "target_node_id": "vessel",
            "relationship": "INVOLVED_IN",
        },
        {
            "source_node_id": "vessel",
            "target_node_id": "unrelated",
            "relationship": "CAUSED",
        },
    ]
    retained = add_structural_passthrough_nodes(
        retained_node_ids={"n1"},
        edges=edges,
    )
    assert retained == {"n1", "vessel"}
    assert "unrelated" not in retained


def test_edge_filter_requires_both_endpoints_retained():
    edges = [
        {"source_node_id": "a", "target_node_id": "b", "relationship": "FOLLOWED_BY"},
        {"source_node_id": "b", "target_node_id": "c", "relationship": "FOLLOWED_BY"},
    ]
    filtered = filter_edges_for_nodes(edges, {"a", "b"})
    assert len(filtered) == 1
    assert filtered[0]["source_node_id"] == "a"
