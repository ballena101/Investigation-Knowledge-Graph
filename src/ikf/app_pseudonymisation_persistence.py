"""Persist reviewed pseudonymised derivatives and reuse them as governed inputs.

This transform builds on app_pseudonymisation_adoption. It stores reviewed
pseudonymised text encrypted in Neo4j, keeps the mapping encrypted separately,
exposes saved derivatives in the document selector for their approved class,
and transparently routes a selected derivative through the existing governed
DirectTextSource pipeline. No second analysis pipeline is introduced.
"""

from __future__ import annotations


PSEUDONYMISATION_PERSISTENCE_VERSION = "IKF_PSEUDONYMISATION_PERSISTENCE_V0.1.1"


def _replace_once(source: str, old: str, new: str, name: str) -> str:
    count = source.count(old)
    if count != 1:
        raise RuntimeError(
            f"Pseudonymisation persistence failed at {name}: "
            f"expected one match, found {count}."
        )
    return source.replace(old, new, 1)


def transform_app_pseudonymisation_persistence(source: str):
    applied = []

    helper_anchor = "\nwith tab_new_analysis:\n"
    helpers = r'''
def save_pseudonymised_derivative(result, title):
    """Persist encrypted reviewed derivative plus encrypted reversible mapping."""
    if not DIRECT_TEXT_ENCRYPTION_KEY:
        raise RuntimeError(
            "DIRECT_TEXT_ENCRYPTION_KEY is not configured; reusable derivatives "
            "cannot be persisted safely."
        )

    text = str(result.get("text") or "").strip()
    if not text:
        raise ValueError("The reviewed pseudonymised derivative is empty.")

    processing_class = str(result.get("processing_class") or "").strip().upper()
    if processing_class not in INFORMATION_CLASSES:
        raise ValueError("The pseudonymised derivative has no valid processing class.")

    derivative_id = "pseudo_" + uuid.uuid4().hex
    safe_title = str(title or "").strip() or "Pseudonymised derivative"
    filename = safe_title if safe_title.lower().endswith(".txt") else safe_title + ".txt"
    text_sha256 = hashlib.sha256(text.encode("utf-8")).hexdigest()
    encrypted_text = encrypt_direct_text(text)
    mapping_payload = json.dumps(
        result.get("mapping") or {},
        ensure_ascii=False,
        sort_keys=True,
    )
    encrypted_mapping = encrypt_direct_text(mapping_payload)
    reviewer = get_reviewer_identity()
    actor = (
        reviewer["email"]
        if reviewer["email"] != "unknown"
        else reviewer["username"]
    )

    with get_driver().session() as session:
        session.run(
            """
            CREATE (d:PseudonymisedDerivative {
                derivative_id: $derivative_id,
                filename: $filename,
                title: $title,
                source_type: 'PSEUDONYMISED_DERIVATIVE',
                privacy_status: 'PSEUDONYMISED_DERIVATIVE',
                source_managed_by: 'IKF',
                catalogue_status: 'AVAILABLE',
                information_class: $information_class,
                source_information_class: $source_information_class,
                source_mode: $source_mode,
                pseudonymisation_version: $pseudonymisation_version,
                selected_categories: $selected_categories,
                parent_source_ids: $parent_source_ids,
                parent_source_labels: $parent_source_labels,
                encrypted_text: $encrypted_text,
                encryption_scheme: 'FERNET',
                text_sha256: $text_sha256,
                encrypted_mapping: $encrypted_mapping,
                mapping_encryption_scheme: 'FERNET',
                review_status: 'REVIEWED_FOR_REUSE',
                created_by: $created_by,
                created_at: datetime()
            })
            """,
            derivative_id=derivative_id,
            filename=filename,
            title=safe_title,
            information_class=processing_class,
            source_information_class=str(
                result.get("source_information_class") or processing_class
            ),
            source_mode=str(result.get("source_mode") or "UNKNOWN"),
            pseudonymisation_version=str(result.get("version") or "UNKNOWN"),
            selected_categories=list(result.get("categories") or []),
            parent_source_ids=list(result.get("parent_source_ids") or []),
            parent_source_labels=list(result.get("parent_source_labels") or []),
            encrypted_text=encrypted_text,
            text_sha256=text_sha256,
            encrypted_mapping=encrypted_mapping,
            created_by=actor,
        ).consume()

        for parent_id in result.get("parent_source_ids") or []:
            session.run(
                """
                MATCH (d:PseudonymisedDerivative {derivative_id: $derivative_id})
                MATCH (p:SourceDocument {document_id: $parent_id})
                MERGE (d)-[:DERIVED_FROM]->(p)
                """,
                derivative_id=derivative_id,
                parent_id=parent_id,
            ).consume()

    return derivative_id


@st.cache_data(ttl=30)
def load_pseudonymised_derivatives(information_class):
    if information_class not in INFORMATION_CLASSES:
        return []
    query = """
    MATCH (d:PseudonymisedDerivative)
    WHERE
        d.catalogue_status = 'AVAILABLE'
        AND d.information_class = $information_class
    RETURN
        d.derivative_id AS document_id,
        d.filename AS filename,
        NULL AS volume_path,
        NULL AS relative_path,
        d.source_type AS source_type,
        NULL AS byte_size,
        NULL AS viewer_source_path,
        'IKF' AS viewer_source_repository,
        d.filename AS viewer_source_filename,
        'IKF' AS source_managed_by,
        d.information_class AS information_class,
        d.source_information_class AS source_information_class,
        coalesce(d.parent_source_ids, []) AS parent_source_ids,
        coalesce(d.parent_source_labels, []) AS parent_source_labels,
        d.pseudonymisation_version AS pseudonymisation_version,
        d.text_sha256 AS sha256,
        true AS is_pseudonymised_derivative,
        'English' AS detected_language
    ORDER BY d.created_at DESC
    """
    with get_driver().session() as session:
        return [
            record.data()
            for record in session.run(
                query,
                information_class=information_class,
            )
        ]


def load_pseudonymised_derivative_text(derivative_id):
    if not DIRECT_TEXT_ENCRYPTION_KEY:
        raise RuntimeError("DIRECT_TEXT_ENCRYPTION_KEY is not configured.")
    with get_driver().session() as session:
        record = session.run(
            """
            MATCH (d:PseudonymisedDerivative {derivative_id: $derivative_id})
            WHERE d.catalogue_status = 'AVAILABLE'
            RETURN
                d.encrypted_text AS encrypted_text,
                d.encryption_scheme AS encryption_scheme,
                d.information_class AS information_class,
                d.source_information_class AS source_information_class,
                coalesce(d.parent_source_ids, []) AS parent_source_ids,
                coalesce(d.parent_source_labels, []) AS parent_source_labels,
                d.pseudonymisation_version AS pseudonymisation_version,
                d.filename AS filename
            """,
            derivative_id=derivative_id,
        ).single()
    if record is None:
        raise ValueError("The pseudonymised derivative is no longer available.")
    if record["encryption_scheme"] != "FERNET":
        raise ValueError("Unsupported pseudonymised derivative encryption scheme.")
    text = Fernet(
        DIRECT_TEXT_ENCRYPTION_KEY.encode("utf-8")
    ).decrypt(
        record["encrypted_text"].encode("utf-8")
    ).decode("utf-8")
    data = record.data()
    data["text"] = text
    return data

'''
    source = _replace_once(
        source,
        helper_anchor,
        "\n" + helpers + helper_anchor,
        "persistent derivative helpers",
    )
    applied.append("persistent_encrypted_derivative_store")

    catalogue_anchor = '''    documents_by_id = {
        document["document_id"]: document
        for document in available_documents
    }

    if classification_selected:
        policy = resolve_model_policy(information_class)
'''
    catalogue_new = '''    if classification_selected:
        available_documents = list(available_documents) + load_pseudonymised_derivatives(
            information_class
        )

    documents_by_id = {
        document["document_id"]: document
        for document in available_documents
    }

    if classification_selected:
        policy = resolve_model_policy(information_class)
'''
    source = _replace_once(
        source,
        catalogue_anchor,
        catalogue_new,
        "derivative catalogue merge",
    )
    applied.append("derivatives_in_document_selector")

    label_anchor = '''    def source_document_label(document_id):
        document = documents_by_id[document_id]
        repository = (
'''
    label_new = '''    def source_document_label(document_id):
        document = documents_by_id[document_id]
        if document.get("is_pseudonymised_derivative"):
            parents = document.get("parent_source_labels") or []
            parent_text = (
                " · derived from " + ", ".join(parents)
                if parents
                else ""
            )
            return (
                f"[IKF · Pseudonymised · Class {document.get('information_class')}] "
                f"{document.get('filename') or document_id}{parent_text}"
            )
        repository = (
'''
    source = _replace_once(
        source,
        label_anchor,
        label_new,
        "derivative selector label",
    )
    applied.append("derivative_parentage_visible_in_selector")

    derivative_read_anchor = '''                    source_path = (
                        document.get("viewer_source_path")
                        or document.get("volume_path")
                    )
                    try:
                        extracted = read_source_text(
                            source_path,
                            allowed_roots=ALLOWED_SOURCE_VOLUME_ROOTS,
                        )
                    except Exception as exc:
                        pseudo_errors.append(
                            f"{document.get('filename') or document_id}: {exc}"
                        )
                        continue
                    filename = document.get("filename") or document_id
                    source_chunks.append(
                        f"[[SOURCE {filename}]]\\n{extracted['text']}"
                    )
'''
    derivative_read_new = '''                    filename = document.get("filename") or document_id
                    try:
                        if document.get("is_pseudonymised_derivative"):
                            extracted = {
                                "text": load_pseudonymised_derivative_text(
                                    document_id
                                )["text"]
                            }
                        else:
                            source_path = (
                                document.get("viewer_source_path")
                                or document.get("volume_path")
                            )
                            extracted = read_source_text(
                                source_path,
                                allowed_roots=ALLOWED_SOURCE_VOLUME_ROOTS,
                            )
                    except Exception as exc:
                        pseudo_errors.append(
                            f"{filename}: {exc}"
                        )
                        continue
                    source_chunks.append(
                        f"[[SOURCE {filename}]]\\n{extracted['text']}"
                    )
'''
    source = _replace_once(
        source,
        derivative_read_anchor,
        derivative_read_new,
        "pseudonymise saved derivative source",
    )
    applied.append("saved_derivative_can_be_reprocessed")

    save_anchor = '''        def _adopt_pseudonymised_derivative():
            result = st.session_state.get("pseudonymisation_result") or {}
'''
    save_ui = '''        derivative_default_title = (
            "Pseudonymised — "
            + (
                ", ".join(parent_labels)
                if parent_labels
                else "direct text"
            )
        )
        derivative_title = st.text_input(
            "Reusable derivative name",
            value=derivative_default_title,
            key="pseudonymised_derivative_title",
        )
        if st.button(
            "Save reviewed derivative as reusable input",
            key="save_pseudonymised_derivative",
        ):
            try:
                derivative_id = save_pseudonymised_derivative(
                    pseudonymisation_result,
                    derivative_title,
                )
                load_pseudonymised_derivatives.clear()
                st.success(
                    "Saved as reusable governed input: " + derivative_id
                )
            except Exception as exc:
                st.error("The reusable derivative could not be saved safely.")
                st.caption(str(exc))

''' + save_anchor
    source = _replace_once(
        source,
        save_anchor,
        save_ui,
        "save derivative action",
    )
    applied.append("reviewed_derivative_save_action")

    create_anchor = '''    if create_submitted:
        errors = []
'''
    create_new = '''    if create_submitted and input_mode == "Documents":
        derivative_ids = [
            document_id
            for document_id in selected_document_ids
            if (documents_by_id.get(document_id) or {}).get(
                "is_pseudonymised_derivative"
            )
        ]
        if derivative_ids:
            if len(derivative_ids) != 1 or len(selected_document_ids) != 1:
                st.error(
                    "For v0.1, analyse one saved pseudonymised derivative at a time; "
                    "do not mix it with original documents in the same analysis."
                )
                create_submitted = False
            else:
                try:
                    derivative = load_pseudonymised_derivative_text(
                        derivative_ids[0]
                    )
                    direct_text = derivative["text"]
                    input_mode = "Direct text"
                    information_class = derivative["information_class"]
                    policy = resolve_model_policy(information_class)
                    st.session_state.pop("transcript_analysis_origin", None)
                    st.session_state["pseudonymised_analysis_origin"] = {
                        "derivative_id": derivative_ids[0],
                        "source_information_class": derivative.get(
                            "source_information_class"
                        ),
                        "processing_class": derivative.get("information_class"),
                        "parent_source_ids": list(
                            derivative.get("parent_source_ids") or []
                        ),
                        "pseudonymisation_version": derivative.get(
                            "pseudonymisation_version"
                        ),
                    }
                except Exception as exc:
                    st.error("The saved pseudonymised derivative could not be opened.")
                    st.caption(str(exc))
                    create_submitted = False

    if create_submitted:
        errors = []
'''
    source = _replace_once(
        source,
        create_anchor,
        create_new,
        "saved derivative analysis routing",
    )
    applied.append("saved_derivative_reuses_direct_text_pipeline")

    return source, tuple(applied)
