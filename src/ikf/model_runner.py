"""Dual-model execution for IKF governed evidence.

Both models receive the exact same evidence text and task instructions.
The function does not validate, persist, or promote model output to the
knowledge graph. Human review remains a separate governed step.
"""

from __future__ import annotations

from typing import Any, Iterable


MODEL_A_SERVICE = "bdw_analysis_prod.kg_poc.ikf-gpt-oss-20b-poc"
MODEL_B_SERVICE = "bdw_analysis_prod.kg_poc.ikf-llama-3-3-70b-poc"
DEFAULT_PROMPT_VERSION = "cf_extraction_v1"


def _build_prompt(item: dict[str, Any]) -> str:
    """Build one shared prompt used unchanged for both models."""

    return f"""You are analysing evidence from a maritime safety investigation.

Task:
Assess only the evidence supplied below. Do not use outside knowledge.
Identify the contributing factor supported by the evidence and preserve
the causal relationship expressed in the source.

Governed query:
- query_id: {item.get("query_id")}
- subject evidence term: {item.get("subject_term")}
- relationship: {item.get("requested_relationship")}
- object evidence term: {item.get("object_term")}

Evidence:
{item.get("evidence_text", "")}

Return a concise answer grounded only in this evidence.
If the evidence does not support a contributing factor, return exactly:
NO_SUPPORTED_CONTRIBUTING_FACTOR
"""


def run_models(
    client: Any,
    query_results: Iterable[dict[str, Any]],
    *,
    prompt_version: str = DEFAULT_PROMPT_VERSION,
    model_a_max_output_tokens: int = 600,
    model_b_max_output_tokens: int = 600,
) -> list[dict[str, Any]]:
    """Run GPT-OSS 20B and Llama 3.3 70B on identical governed evidence."""

    outputs: list[dict[str, Any]] = []

    for item in query_results:
        prompt = _build_prompt(item)

        # Model A: GPT-OSS via Responses API.
        response_a = client.responses.create(
            model=MODEL_A_SERVICE,
            input=prompt,
            max_output_tokens=model_a_max_output_tokens,
        )

        # Model B: Llama via Chat Completions API.
        response_b = client.chat.completions.create(
            model=MODEL_B_SERVICE,
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            max_tokens=model_b_max_output_tokens,
        )

        outputs.append(
            {
                "query_id": item.get("query_id"),
                "query_spec_id": item.get("query_spec_id"),
                "passage_id": item.get("passage_id"),
                "document_id": item.get("document_id"),
                "report_package_id": item.get("report_package_id"),
                "evidence_text": item.get("evidence_text"),
                "evidence_text_sha256": item.get("evidence_text_sha256"),
                "source_passage_text_sha256": item.get(
                    "source_passage_text_sha256"
                ),
                "prompt_version": prompt_version,
                "prompt_text": prompt,
                "model_a_service": MODEL_A_SERVICE,
                "model_a_api_method": "responses.create",
                "model_a_underlying_model": getattr(response_a, "model", None),
                "model_a_finish_status": getattr(response_a, "status", None),
                "model_a_answer": response_a.output_text,
                "model_a_max_output_tokens": model_a_max_output_tokens,
                "model_b_service": MODEL_B_SERVICE,
                "model_b_api_method": "chat.completions.create",
                "model_b_underlying_model": getattr(response_b, "model", None),
                "model_b_finish_status": (
                    response_b.choices[0].finish_reason
                    if response_b.choices
                    else None
                ),
                "model_b_answer": (
                    response_b.choices[0].message.content
                    if response_b.choices
                    else None
                ),
                "model_b_max_output_tokens": model_b_max_output_tokens,
            }
        )

    return outputs
