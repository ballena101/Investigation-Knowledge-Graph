"""Transitional App adoption helpers for IKF shared governance modules.

The Streamlit application predates the reusable ``src/ikf`` package and still
contains duplicated deterministic rules. This module provides two things:

1. small legacy-shape adapters used by the current App; and
2. a deterministic source transformer that replaces duplicated policy blocks
   with calls to the shared modules without rewriting the whole Streamlit file
   in one risky change.

The transformer is intentionally strict. When the App source drifts and an
expected block cannot be located, it raises rather than silently leaving a
second policy implementation active.
"""

from __future__ import annotations

import re
from typing import Iterable

from .emcip_governance import validate_human_emcip_review
from .evidence_locations import parse_evidence_location as _parse_location
from .graph_governance import (
    add_structural_passthrough_nodes,
    filter_edges_for_nodes,
    relationship_semantics,
)
from .question_scope import resolve_effective_document_scope
from .retention import analysis_content_retention_hours as shared_content_retention_hours
from .review_governance import validate_human_relationship_review
from .shield_governance import validate_gate2_review
from .source_routing import filter_catalogue_rows, resolve_source_route


ADOPTION_VERSION = "IKF_APP_SHARED_POLICY_ADOPTION_V0.2"


def legacy_parse_evidence_location(value):
    """Return the App's historical dict/None shape using the strict parser."""

    try:
        location = _parse_location(value)
    except (TypeError, ValueError):
        return None

    return {
        "document_id": location.document_id,
        "page_start": location.page_start,
        "page_end": location.page_end,
    }


def _document_ids_from_locations(values: Iterable[str]) -> set[str]:
    result: set[str] = set()
    for value in values or []:
        parsed = legacy_parse_evidence_location(value)
        if parsed:
            result.add(parsed["document_id"])
    return result


def scope_graph_by_documents(raw_graph: dict, selected_document_ids) -> dict:
    """Apply evidence scope while retaining structural connector nodes.

    Evidence-bearing nodes and evidence-bearing relationship endpoints are the
    semantic seed. Structural relationships may add connector nodes, but they
    do not independently pull unrelated semantic content into scope.
    """

    selected = {str(value) for value in selected_document_ids or [] if value}
    nodes = list(raw_graph.get("nodes") or [])
    edges = list(raw_graph.get("edges") or [])

    if not selected:
        return {"nodes": nodes, "edges": edges}

    seed_node_ids = {
        node["node_id"]
        for node in nodes
        if _document_ids_from_locations(node.get("evidence_locations")) & selected
    }

    evidence_edges = [
        edge
        for edge in edges
        if _document_ids_from_locations(edge.get("evidence_locations")) & selected
    ]

    for edge in evidence_edges:
        seed_node_ids.add(edge["source_id"])
        seed_node_ids.add(edge["target_id"])

    governance_edges = [
        {
            "source_node_id": edge.get("source_id"),
            "target_node_id": edge.get("target_id"),
            "relationship": edge.get("relationship"),
        }
        for edge in edges
    ]
    retained_node_ids = add_structural_passthrough_nodes(
        retained_node_ids=seed_node_ids,
        edges=governance_edges,
    )

    scoped_nodes = [
        node for node in nodes if node.get("node_id") in retained_node_ids
    ]

    evidence_edge_ids = {edge.get("edge_id") for edge in evidence_edges}
    candidate_edges = [
        edge
        for edge in edges
        if edge.get("edge_id") in evidence_edge_ids
        or relationship_semantics(edge.get("relationship")) == "STRUCTURAL"
    ]
    normalized = [
        {
            **edge,
            "source_node_id": edge.get("source_id"),
            "target_node_id": edge.get("target_id"),
        }
        for edge in candidate_edges
    ]
    filtered = filter_edges_for_nodes(normalized, retained_node_ids)

    scoped_edges = [
        {
            key: value
            for key, value in edge.items()
            if key not in {"source_node_id", "target_node_id"}
        }
        for edge in filtered
    ]

    return {"nodes": scoped_nodes, "edges": scoped_edges}


def _candidate_id(candidate: dict | None) -> str | None:
    if not candidate:
        return None
    for key in ("candidate_id", "code_idcode", "idCode", "idcode"):
        value = candidate.get(key)
        if value:
            return str(value)
    return None


def validate_app_emcip_review(
    *,
    proposal: dict,
    decision: str,
    amended_candidate: dict | None,
):
    shortlist = proposal.get("candidate_options") or []
    shortlist_ids = [_candidate_id(item) for item in shortlist]
    proposed_id = str(proposal.get("proposed_code_idcode") or "").strip() or None
    amended_id = _candidate_id(amended_candidate)
    return validate_human_emcip_review(
        decision=decision,
        proposed_candidate_id=proposed_id,
        shortlist_candidate_ids=shortlist_ids,
        amended_candidate_id=amended_id,
    )


def validate_app_shield_review(
    *,
    proposal: dict,
    decision: str,
    amended_label: str | None,
):
    if not proposal.get("gate_is_current"):
        raise ValueError(
            "The Gate-1 relationship review has changed. Regenerate SHIELD proposals before reviewing this item."
        )
    if proposal.get("assistant_status") != "ASSISTANT_PROPOSED":
        raise ValueError(
            "Only a grounded assistant SHIELD proposal can enter Gate 2 review."
        )
    return validate_gate2_review(
        decision=decision,
        proposed_label=proposal.get("proposed_shield_label"),
        amended_label=amended_label,
    )


def _replace_once(
    source: str,
    pattern: str,
    replacement: str,
    *,
    name: str,
    flags=0,
):
    updated, count = re.subn(pattern, replacement, source, count=1, flags=flags)
    if count != 1:
        raise RuntimeError(
            f"Shared-policy App adoption failed at {name}: expected exactly one match, found {count}."
        )
    return updated


def transform_app_source(source: str) -> tuple[str, tuple[str, ...]]:
    """Replace duplicated App policy blocks with shared-module calls.

    This is a transitional refactor mechanism. It is deterministic, compileable
    and covered by local tests; the final target remains a physically smaller
    modular Streamlit source tree.
    """

    applied: list[str] = []

    import_anchor = "from streamlit_cytoscape import (\n    streamlit_cytoscape,\n    NodeStyle,\n    EdgeStyle,\n)\n"
    shared_imports = import_anchor + "\nfrom ikf.app_adoption import (\n    legacy_parse_evidence_location,\n    scope_graph_by_documents,\n    shared_content_retention_hours,\n    filter_catalogue_rows,\n    resolve_source_route,\n    resolve_effective_document_scope,\n    validate_human_relationship_review,\n    validate_app_shield_review,\n    validate_app_emcip_review,\n)\n"
    if import_anchor not in source:
        raise RuntimeError("Shared-policy App adoption could not locate the import anchor.")
    source = source.replace(import_anchor, shared_imports, 1)
    applied.append("shared_imports")

    endpoint_anchor = (
        'CLASS_D_GPT20_ENDPOINT = os.getenv("CLASS_D_GPT20_ENDPOINT")\n'
        'CLASS_D_LLAMA70_ENDPOINT = (\n'
        '    os.getenv("CLASS_D_LLAMA70_ENDPOINT")\n'
        '    or os.getenv("CLASS_D_OLLAMA_LLAMA70_URL")\n'
        ')\n'
    )
    endpoint_replacement = (
        'CLASS_D_GPT20_ENDPOINT = os.getenv("CLASS_D_GPT20_ENDPOINT")\n'
        'CLASS_D_OLLAMA_LLAMA70_URL = os.getenv("CLASS_D_OLLAMA_LLAMA70_URL")\n'
        'CLASS_D_LLAMA70_ENDPOINT = (\n'
        '    os.getenv("CLASS_D_LLAMA70_ENDPOINT")\n'
        '    or CLASS_D_OLLAMA_LLAMA70_URL\n'
        ')\n'
    )
    if endpoint_anchor not in source:
        raise RuntimeError(
            "Shared-policy App adoption could not locate the Class-D Llama endpoint anchor."
        )
    source = source.replace(endpoint_anchor, endpoint_replacement, 1)
    applied.append("class_d_llama_alias")

    source = _replace_once(
        source,
        r"def content_retention_hours\(information_class\):\n    return \(\n        CLASS_D_CONTENT_RETENTION_HOURS\n        if information_class == \"D\"\n        else OTHER_CONTENT_RETENTION_HOURS\n    \)\n",
        "def content_retention_hours(information_class):\n    return shared_content_retention_hours(information_class)\n",
        name="retention_policy",
    )
    applied.append("retention_policy")

    source = _replace_once(
        source,
        r"def parse_evidence_location\(value\):\n    \"\"\"Parse document_id\|page_start\|page_end emitted by notebook 16\.\"\"\"\n(?:.|\n)*?\n\n\ndef pdf_page_range_bytes",
        "def parse_evidence_location(value):\n    return legacy_parse_evidence_location(value)\n\n\ndef pdf_page_range_bytes",
        name="evidence_location_parser",
    )
    applied.append("evidence_location_parser")

    catalogue_pattern = r"    # CLASSIFICATION_DRIVEN_CATALOGUE\n(?:.|\n)*?    documents_by_id = \{\n        document\[\"document_id\"\]: document\n        for document in available_documents\n    \}\n"
    catalogue_replacement = "    # CLASSIFICATION_DRIVEN_CATALOGUE — shared deterministic policy\n    source_route = resolve_source_route(information_class, \"DOCUMENTS\")\n    available_documents = filter_catalogue_rows(\n        source_documents,\n        information_class=information_class,\n    )\n    catalogue_scope_label = (\n        \"MAIRA published investigation material\"\n        if source_route.catalogue_scope == \"MAIRA_PUBLISHED_INVESTIGATION_MATERIAL\"\n        else \"IKF document library\"\n    )\n\n    documents_by_id = {\n        document[\"document_id\"]: document\n        for document in available_documents\n    }\n"
    source = _replace_once(
        source,
        catalogue_pattern,
        catalogue_replacement,
        name="source_catalogue_routing",
    )
    applied.append("source_catalogue_routing")

    question_anchor = "    if analysis.get(\"status\") != \"COMPLETED\":\n        raise ValueError(\n            \"Questions can currently be asked only against a completed analysis.\"\n        )\n\n"
    question_replacement = question_anchor + "    analysis_document_ids = [\n        item[\"document_id\"]\n        for item in load_analysis_sources(analysis[\"analysis_id\"])\n        if item.get(\"document_id\")\n    ]\n    resolved_scope = resolve_effective_document_scope(\n        scope_mode=scope_mode,\n        analysis_document_ids=analysis_document_ids,\n        scope_document_ids=scope_document_ids,\n    )\n    scope_mode = resolved_scope.scope_mode\n    scope_document_ids = (\n        []\n        if scope_mode == \"WHOLE_CASE\"\n        else list(resolved_scope.effective_document_ids)\n    )\n\n"
    if question_anchor not in source:
        raise RuntimeError("Shared-policy App adoption could not locate QuestionRun scope anchor.")
    source = source.replace(question_anchor, question_replacement, 1)
    applied.append("question_scope")

    relationship_anchor = "    reviewer = get_reviewer_identity()\n\n    status_by_decision = {\n        \"VALIDATED\": \"HUMAN_VALIDATED\",\n        \"REJECTED\": \"HUMAN_REJECTED\",\n        \"AMENDED\": \"HUMAN_AMENDED\",\n    }\n\n    review_id = str(uuid.uuid4())\n"
    relationship_replacement = "    validated_review = validate_human_relationship_review(\n        relationship=edge[\"relationship\"],\n        decision=decision,\n        amended_relationship=amended_relationship,\n    )\n    decision = validated_review.decision\n    amended_relationship = validated_review.amended_relationship\n    reviewer = get_reviewer_identity()\n\n    status_by_decision = {\n        \"VALIDATED\": \"HUMAN_VALIDATED\",\n        \"REJECTED\": \"HUMAN_REJECTED\",\n        \"AMENDED\": \"HUMAN_AMENDED\",\n    }\n\n    review_id = str(uuid.uuid4())\n"
    if relationship_anchor not in source:
        raise RuntimeError("Shared-policy App adoption could not locate relationship review anchor.")
    source = source.replace(relationship_anchor, relationship_replacement, 1)
    applied.append("relationship_review")

    shield_pattern = r"def save_shield_review\(\n    proposal,\n    \*,\n    decision,\n    amended_label,\n    amended_code,\n    amended_path,\n    comment,\n\):\n(?:.|\n)*?    reviewer = get_reviewer_identity\(\)\n"
    shield_replacement = "def save_shield_review(\n    proposal,\n    *,\n    decision,\n    amended_label,\n    amended_code,\n    amended_path,\n    comment,\n):\n    validated_review = validate_app_shield_review(\n        proposal=proposal,\n        decision=decision,\n        amended_label=amended_label,\n    )\n    decision = validated_review.decision\n    amended_label = validated_review.amended_label\n    reviewer = get_reviewer_identity()\n"
    source = _replace_once(
        source,
        shield_pattern,
        shield_replacement,
        name="shield_gate2",
    )
    applied.append("shield_gate2")

    emcip_anchor = "def save_analysis_mapping_review(\n    proposal,\n    decision,\n    amended_candidate,\n    comment,\n):\n    reviewer = get_reviewer_identity()\n"
    emcip_replacement = "def save_analysis_mapping_review(\n    proposal,\n    decision,\n    amended_candidate,\n    comment,\n):\n    validated_review = validate_app_emcip_review(\n        proposal=proposal,\n        decision=decision,\n        amended_candidate=amended_candidate,\n    )\n    decision = validated_review.decision\n    reviewer = get_reviewer_identity()\n"
    if emcip_anchor not in source:
        raise RuntimeError("Shared-policy App adoption could not locate EMCIP review anchor.")
    source = source.replace(emcip_anchor, emcip_replacement, 1)
    applied.append("emcip_review")

    graph_pattern = r"        if document_filter_active:\n(?:.|\n)*?\n        available_node_kinds = sorted\("
    graph_replacement = "        if document_filter_active:\n            scoped_graph = scope_graph_by_documents(\n                raw_graph,\n                selected_graph_document_ids,\n            )\n            scoped_nodes = scoped_graph[\"nodes\"]\n            scoped_edges = scoped_graph[\"edges\"]\n\n        available_node_kinds = sorted("
    source = _replace_once(
        source,
        graph_pattern,
        graph_replacement,
        name="graph_document_scope",
    )
    applied.append("graph_document_scope")

    return source, tuple(applied)
