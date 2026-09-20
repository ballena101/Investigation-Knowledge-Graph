# Databricks notebook source
# MAGIC %md
# MAGIC # 15 — Extract selected analysis documents
# MAGIC
# MAGIC First real processing stage for the generic Investigation Knowledge Graph.
# MAGIC
# MAGIC **Input:** one `AnalysisGroup` created in the App, containing either
# MAGIC 1–5 `SourceDocument` nodes or one temporary `DirectTextSource`.
# MAGIC
# MAGIC **Output:**
# MAGIC - source text extracted under the current Databricks user's permissions;
# MAGIC - deterministic passages persisted to
# MAGIC   `bdw_analysis_prod.kg_poc.analysis_passage`;
# MAGIC - source-document language and extraction metadata updated in Neo4j;
# MAGIC - live processing counters/status updated on the `AnalysisGroup`.
# MAGIC
# MAGIC This notebook builds the **evidence layer only**. It does not infer causal
# MAGIC relationships. The next stage will analyse the evidence group.

# COMMAND ----------

dbutils.widgets.text(
    "analysis_id",
    "",
    "Analysis ID",
)

# COMMAND ----------

# MAGIC %pip install neo4j==6.3.1 pymupdf==1.26.4 python-docx==1.2.0 langdetect==1.0.9 cryptography==46.0.2

# COMMAND ----------

dbutils.library.restartPython()

# COMMAND ----------

import hashlib
import os
import re
from collections import Counter
from datetime import datetime, timezone

import fitz  # PyMuPDF
from cryptography.fernet import Fernet
from docx import Document as DocxDocument
from langdetect import DetectorFactory, LangDetectException, detect
from neo4j import GraphDatabase
from pyspark.sql import Row

DetectorFactory.seed = 0

ANALYSIS_PASSAGE_TABLE = "bdw_analysis_prod.kg_poc.analysis_passage"
EXTRACTION_VERSION = "EVIDENCE_EXTRACTION_V0.1"
MAX_DOCUMENTS_PER_ANALYSIS = 5
TARGET_PASSAGE_CHARS = 2400
MAX_PASSAGE_CHARS = 3600

analysis_id = dbutils.widgets.get("analysis_id").strip()

if not re.fullmatch(r"analysis_[0-9a-f]{32}", analysis_id):
    raise ValueError(
        "Enter a valid analysis_id created by the App, for example "
        "'analysis_<32 hex characters>'."
    )

print("Analysis:", analysis_id)

# COMMAND ----------

try:
    NEO4J_URI
    NEO4J_USERNAME
    NEO4J_PASSWORD
except NameError:
    NEO4J_URI = dbutils.secrets.get(
        scope="kg-poc-app",
        key="neo4j_uri",
    )
    NEO4J_USERNAME = dbutils.secrets.get(
        scope="kg-poc-app",
        key="neo4j_username",
    )
    NEO4J_PASSWORD = dbutils.secrets.get(
        scope="kg-poc-app",
        key="neo4j_password",
    )

driver = GraphDatabase.driver(
    NEO4J_URI,
    auth=(NEO4J_USERNAME, NEO4J_PASSWORD),
)

driver.verify_connectivity()
print("Neo4j connection: OK")

DIRECT_TEXT_ENCRYPTION_KEY = dbutils.secrets.get(
    scope="kg-poc-app",
    key="direct_text_encryption_key",
)

# COMMAND ----------

def update_analysis_status(
    *,
    status,
    stage,
    documents_total=None,
    documents_processed=None,
    pages_total=None,
    pages_processed=None,
    passages_total=None,
    error_message=None,
):
    query = """
    MATCH (a:AnalysisGroup {analysis_id: $analysis_id})
    SET
        a.status = $status,
        a.processing_stage = $stage,
        a.processing_updated_at = datetime(),
        a.processing_error = $error_message
    FOREACH (_ IN CASE WHEN $documents_total IS NULL THEN [] ELSE [1] END |
        SET a.documents_total = $documents_total
    )
    FOREACH (_ IN CASE WHEN $documents_processed IS NULL THEN [] ELSE [1] END |
        SET a.documents_processed = $documents_processed
    )
    FOREACH (_ IN CASE WHEN $pages_total IS NULL THEN [] ELSE [1] END |
        SET a.pages_total = $pages_total
    )
    FOREACH (_ IN CASE WHEN $pages_processed IS NULL THEN [] ELSE [1] END |
        SET a.pages_processed = $pages_processed
    )
    FOREACH (_ IN CASE WHEN $passages_total IS NULL THEN [] ELSE [1] END |
        SET a.passages_total = $passages_total
    )
    RETURN a.analysis_id AS analysis_id
    """

    params = {
        "analysis_id": analysis_id,
        "status": status,
        "stage": stage,
        "documents_total": documents_total,
        "documents_processed": documents_processed,
        "pages_total": pages_total,
        "pages_processed": pages_processed,
        "passages_total": passages_total,
        "error_message": error_message,
    }

    with driver.session() as session:
        session.run(query, **params).consume()


def load_analysis_sources():
    query = """
    MATCH (a:AnalysisGroup {analysis_id: $analysis_id})
    OPTIONAL MATCH (a)-[:HAS_SOURCE]->(d:SourceDocument)
    OPTIONAL MATCH (a)-[:HAS_SOURCE_TEXT]->(t:DirectTextSource)
    WITH a, collect(DISTINCT d) AS documents, head(collect(DISTINCT t)) AS text_source
    RETURN
        a.analysis_id AS analysis_id,
        a.analysis_title AS analysis_title,
        properties(a)["input_mode"] AS input_mode,
        properties(a)["information_class"] AS information_class,
        a.language_mode AS language_mode,
        a.output_language AS output_language,
        CASE
            WHEN text_source IS NULL THEN NULL
            ELSE {
                source_id: text_source.source_id,
                source_type: text_source.source_type,
                encrypted_text: text_source.encrypted_text,
                encryption_scheme: text_source.encryption_scheme,
                text_sha256: text_source.text_sha256
            }
        END AS text_source,
        [
            d IN documents
            WHERE d IS NOT NULL |
            {
                document_id: d.document_id,
                filename: d.filename,
                volume_path: d.volume_path,
                source_type: d.source_type,
                sha256: d.sha256
            }
        ] AS documents
    """

    with driver.session() as session:
        record = session.run(
            query,
            analysis_id=analysis_id,
        ).single()

    return record.data() if record else None


analysis = load_analysis_sources()

if analysis is None:
    raise ValueError(
        f"AnalysisGroup not found in Neo4j: {analysis_id}"
    )

documents = analysis["documents"] or []
input_mode = analysis.get("input_mode") or "DOCUMENTS"
text_source = analysis.get("text_source")

if input_mode == "DIRECT_TEXT":
    if not text_source or not text_source.get("encrypted_text"):
        raise ValueError(
            "The analysis is configured for direct text but no encrypted "
            "DirectTextSource payload is available."
        )

    if text_source.get("encryption_scheme") != "FERNET":
        raise ValueError(
            "Unsupported DirectTextSource encryption scheme."
        )

    text_source["text_content"] = Fernet(
        DIRECT_TEXT_ENCRYPTION_KEY.encode("utf-8")
    ).decrypt(
        text_source["encrypted_text"].encode("utf-8")
    ).decode("utf-8")
else:
    if not documents:
        raise ValueError(
            "The analysis contains no linked SourceDocument nodes."
        )

    if len(documents) > MAX_DOCUMENTS_PER_ANALYSIS:
        raise ValueError(
            f"This PoC supports a maximum of {MAX_DOCUMENTS_PER_ANALYSIS} "
            f"documents per analysis; found {len(documents)}."
        )

print("Title:", analysis["analysis_title"])
print("Input mode:", input_mode)

if input_mode == "DIRECT_TEXT":
    print("Direct text source:", text_source["source_id"])
else:
    print("Documents:", len(documents))
    for document in documents:
        print(
            " -",
            document["filename"],
            "→",
            document["volume_path"],
        )

# COMMAND ----------

LANGUAGE_NAMES = {
    "af": "Afrikaans",
    "ar": "Arabic",
    "bg": "Bulgarian",
    "ca": "Catalan",
    "cs": "Czech",
    "cy": "Welsh",
    "da": "Danish",
    "de": "German",
    "el": "Greek",
    "en": "English",
    "es": "Spanish",
    "et": "Estonian",
    "fa": "Persian",
    "fi": "Finnish",
    "fr": "French",
    "he": "Hebrew",
    "hi": "Hindi",
    "hr": "Croatian",
    "hu": "Hungarian",
    "id": "Indonesian",
    "is": "Icelandic",
    "it": "Italian",
    "ja": "Japanese",
    "ko": "Korean",
    "lt": "Lithuanian",
    "lv": "Latvian",
    "mk": "Macedonian",
    "nl": "Dutch",
    "no": "Norwegian",
    "pl": "Polish",
    "pt": "Portuguese",
    "ro": "Romanian",
    "ru": "Russian",
    "sk": "Slovak",
    "sl": "Slovenian",
    "so": "Somali",
    "sq": "Albanian",
    "sv": "Swedish",
    "sw": "Swahili",
    "th": "Thai",
    "tl": "Tagalog",
    "tr": "Turkish",
    "uk": "Ukrainian",
    "ur": "Urdu",
    "vi": "Vietnamese",
    "zh-cn": "Chinese",
    "zh-tw": "Chinese",
}


def normalize_text(text):
    if not text:
        return ""

    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def detect_language_name(text):
    sample = normalize_text(text)

    if len(sample) < 80:
        return "UNKNOWN"

    try:
        code = detect(sample[:12000])
    except LangDetectException:
        return "UNKNOWN"

    return LANGUAGE_NAMES.get(code, code)


def split_text(text):
    text = normalize_text(text)

    if not text:
        return []

    paragraphs = [
        paragraph.strip()
        for paragraph in re.split(r"\n\s*\n", text)
        if paragraph.strip()
    ]

    if not paragraphs:
        paragraphs = [text]

    chunks = []
    current = ""

    def flush_current():
        nonlocal current
        if current.strip():
            chunks.append(current.strip())
        current = ""

    for paragraph in paragraphs:
        if len(paragraph) > MAX_PASSAGE_CHARS:
            flush_current()

            start = 0
            while start < len(paragraph):
                end = min(
                    start + MAX_PASSAGE_CHARS,
                    len(paragraph),
                )

                if end < len(paragraph):
                    boundary = paragraph.rfind(
                        ". ",
                        start + TARGET_PASSAGE_CHARS,
                        end,
                    )
                    if boundary > start:
                        end = boundary + 1

                piece = paragraph[start:end].strip()
                if piece:
                    chunks.append(piece)

                start = end

            continue

        candidate = (
            paragraph
            if not current
            else current + "\n\n" + paragraph
        )

        if len(candidate) <= TARGET_PASSAGE_CHARS:
            current = candidate
        elif len(candidate) <= MAX_PASSAGE_CHARS:
            current = candidate
            flush_current()
        else:
            flush_current()
            current = paragraph

    flush_current()
    return chunks


def extract_pdf(path):
    document = fitz.open(path)

    try:
        pages = []

        for index in range(document.page_count):
            page = document.load_page(index)

            # Same deterministic PyMuPDF extraction principle used by MAIRA:
            # preserve page boundaries and request sorted text.
            text = normalize_text(
                page.get_text(
                    "text",
                    sort=True,
                )
            )

            pages.append(
                {
                    "page_number": index + 1,
                    "text": text,
                }
            )

        return pages
    finally:
        document.close()


def extract_docx(path):
    document = DocxDocument(path)

    text = "\n\n".join(
        paragraph.text.strip()
        for paragraph in document.paragraphs
        if paragraph.text.strip()
    )

    return [
        {
            "page_number": 1,
            "text": normalize_text(text),
        }
    ]


def extract_txt(path):
    with open(
        path,
        "r",
        encoding="utf-8",
        errors="replace",
    ) as handle:
        text = handle.read()

    return [
        {
            "page_number": 1,
            "text": normalize_text(text),
        }
    ]


def extract_document(document):
    path = document["volume_path"]
    source_type = (
        document.get("source_type")
        or os.path.splitext(path)[1].lstrip(".")
    ).upper()

    if not os.path.isfile(path):
        raise FileNotFoundError(
            f"Source file is not readable: {path}"
        )

    if source_type == "PDF":
        return extract_pdf(path)

    if source_type == "DOCX":
        return extract_docx(path)

    if source_type == "TXT":
        return extract_txt(path)

    raise ValueError(
        f"Unsupported source type for extraction: {source_type}"
    )


def extract_direct_text(source):
    return [
        {
            "page_number": 1,
            "text": normalize_text(
                source["text_content"]
            ),
        }
    ]


def count_document_pages(document):
    path = document["volume_path"]
    source_type = (
        document.get("source_type")
        or os.path.splitext(path)[1].lstrip(".")
    ).upper()

    if source_type == "PDF":
        pdf = fitz.open(path)
        try:
            return pdf.page_count
        finally:
            pdf.close()

    if source_type in {"DOCX", "TXT"}:
        return 1

    return 0


def passage_id_for(
    document_id,
    page_number,
    passage_order,
    text_sha256,
):
    raw = (
        f"{document_id}|{page_number}|"
        f"{passage_order}|{text_sha256}"
    )

    digest = hashlib.sha256(
        raw.encode("utf-8")
    ).hexdigest()[:24]

    return f"passage_{digest}"

# COMMAND ----------

created_at = datetime.now(timezone.utc)

try:
    if input_mode == "DIRECT_TEXT":
        pages_total = 1
        documents_total = 1
    else:
        pages_total = sum(
            count_document_pages(document)
            for document in documents
        )
        documents_total = len(documents)

    update_analysis_status(
        status="EXTRACTING",
        stage="EXTRACTING",
        documents_total=documents_total,
        documents_processed=0,
        pages_total=pages_total,
        pages_processed=0,
        passages_total=0,
        error_message=None,
    )

    # Reruns are deterministic: replace only this analysis's evidence rows.
    spark.sql(
        f"""
        DELETE FROM {ANALYSIS_PASSAGE_TABLE}
        WHERE analysis_id = '{analysis_id}'
        """
    )

    passage_rows = []
    pages_processed = 0
    documents_processed = 0

    if input_mode == "DIRECT_TEXT":
        source_id = text_source["source_id"]
        pages = extract_direct_text(text_source)
        passage_order = 0
        document_passage_count = 0

        for page in pages:
            page_number = page["page_number"]
            page_text = page["text"]

            chunks = split_text(page_text)

            for chunk in chunks:
                passage_order += 1
                text_sha256 = hashlib.sha256(
                    chunk.encode("utf-8")
                ).hexdigest()

                passage_rows.append(
                    Row(
                        analysis_id=analysis_id,
                        document_id=source_id,
                        passage_id=passage_id_for(
                            source_id,
                            page_number,
                            passage_order,
                            text_sha256,
                        ),
                        page_start=page_number,
                        page_end=page_number,
                        passage_order=passage_order,
                        passage_text=chunk,
                        text_sha256=text_sha256,
                        extraction_version=EXTRACTION_VERSION,
                        created_at=created_at,
                        detected_language=detect_language_name(
                            chunk
                        ),
                    )
                )
                document_passage_count += 1

            pages_processed += 1

        documents_processed = 1

        update_analysis_status(
            status="EXTRACTING",
            stage="EXTRACTING",
            documents_total=1,
            documents_processed=1,
            pages_total=1,
            pages_processed=1,
            passages_total=len(passage_rows),
        )

        print(
            "Direct text passages:",
            document_passage_count,
        )

    else:
        for document in documents:
            print("")
            print("Extracting:", document["filename"])

            pages = extract_document(document)
            document_text = []
            document_passage_count = 0
            passage_order = 0

            for page in pages:
                page_number = page["page_number"]
                page_text = page["text"]

                if page_text:
                    document_text.append(page_text)

                chunks = split_text(page_text)

                for chunk in chunks:
                    passage_order += 1
                    text_sha256 = hashlib.sha256(
                        chunk.encode("utf-8")
                    ).hexdigest()

                    passage_rows.append(
                        Row(
                            analysis_id=analysis_id,
                            document_id=document["document_id"],
                            passage_id=passage_id_for(
                                document["document_id"],
                                page_number,
                                passage_order,
                                text_sha256,
                            ),
                            page_start=page_number,
                            page_end=page_number,
                            passage_order=passage_order,
                            passage_text=chunk,
                            text_sha256=text_sha256,
                            extraction_version=EXTRACTION_VERSION,
                            created_at=created_at,
                            detected_language=detect_language_name(
                                chunk
                            ),
                        )
                    )

                    document_passage_count += 1

                pages_processed += 1

                if (
                    pages_processed % 10 == 0
                    or pages_processed == pages_total
                ):
                    update_analysis_status(
                        status="EXTRACTING",
                        stage="EXTRACTING",
                        documents_total=documents_total,
                        documents_processed=documents_processed,
                        pages_total=pages_total,
                        pages_processed=pages_processed,
                        passages_total=len(passage_rows),
                    )

            full_document_text = "\n\n".join(
                document_text
            )

            document_language = detect_language_name(
                full_document_text
            )

            with driver.session() as session:
                session.run(
                    """
                    MATCH (d:SourceDocument {
                        document_id: $document_id
                    })
                    SET
                        d.detected_language = $detected_language,
                        d.page_count = $page_count,
                        d.passage_count = $passage_count,
                        d.extraction_status = 'EXTRACTED',
                        d.extraction_version = $extraction_version,
                        d.extracted_at = datetime()
                    """,
                    document_id=document["document_id"],
                    detected_language=document_language,
                    page_count=len(pages),
                    passage_count=document_passage_count,
                    extraction_version=EXTRACTION_VERSION,
                ).consume()

            documents_processed += 1

            update_analysis_status(
                status="EXTRACTING",
                stage="EXTRACTING",
                documents_total=documents_total,
                documents_processed=documents_processed,
                pages_total=pages_total,
                pages_processed=pages_processed,
                passages_total=len(passage_rows),
            )

            print(
                "  pages:",
                len(pages),
                "| passages:",
                document_passage_count,
                "| language:",
                document_language,
            )

    if passage_rows:
        passage_schema = spark.table(
            ANALYSIS_PASSAGE_TABLE
        ).schema

        passage_df = spark.createDataFrame(
            passage_rows,
            schema=passage_schema,
        )

        passage_df.write.mode("append").saveAsTable(
            ANALYSIS_PASSAGE_TABLE
        )

    # Privacy-by-design: after governed passages are persisted, remove raw
    # direct text from Neo4j. Keep only its hash and processing metadata.
    if input_mode == "DIRECT_TEXT":
        direct_language = detect_language_name(
            text_source["text_content"]
        )
        with driver.session() as session:
            session.run(
                """
                MATCH (s:DirectTextSource {
                    source_id: $source_id
                })
                REMOVE s.encrypted_text
                SET
                    s.detected_language = $detected_language,
                    s.passage_count = $passage_count,
                    s.extraction_status = 'EXTRACTED_AND_PURGED',
                    s.retention_status = 'ENCRYPTED_PAYLOAD_PURGED',
                    s.extraction_version = $extraction_version,
                    s.extracted_at = datetime()
                """,
                source_id=text_source["source_id"],
                detected_language=direct_language,
                passage_count=len(passage_rows),
                extraction_version=EXTRACTION_VERSION,
            ).consume()

    detected_languages = Counter(
        row.detected_language
        for row in passage_rows
        if row.detected_language not in {
            None,
            "UNKNOWN",
        }
    )

    dominant_language = (
        detected_languages.most_common(1)[0][0]
        if detected_languages
        else "UNKNOWN"
    )

    with driver.session() as session:
        session.run(
            """
            MATCH (a:AnalysisGroup {
                analysis_id: $analysis_id
            })
            SET
                a.status = 'EVIDENCE_READY',
                a.processing_stage = 'EVIDENCE_READY',
                a.documents_total = $documents_total,
                a.documents_processed = $documents_processed,
                a.pages_total = $pages_total,
                a.pages_processed = $pages_processed,
                a.passages_total = $passages_total,
                a.detected_language = $detected_language,
                a.extraction_version = $extraction_version,
                a.evidence_ready_at = datetime(),
                a.processing_updated_at = datetime(),
                a.processing_error = NULL
            """,
            analysis_id=analysis_id,
            documents_total=documents_total,
            documents_processed=documents_processed,
            pages_total=pages_total,
            pages_processed=pages_processed,
            passages_total=len(passage_rows),
            detected_language=dominant_language,
            extraction_version=EXTRACTION_VERSION,
        ).consume()

    print("")
    print("EVIDENCE EXTRACTION COMPLETE")
    print("status: EVIDENCE_READY")
    print("documents:", documents_processed, "/", documents_total)
    print("pages:", pages_processed, "/", pages_total)
    print("passages:", len(passage_rows))
    print("dominant passage language:", dominant_language)

except Exception as exc:
    update_analysis_status(
        status="FAILED",
        stage="EXTRACTION_FAILED",
        error_message=f"{type(exc).__name__}: {exc}",
    )
    raise

finally:
    driver.close()

# COMMAND ----------

display(
    spark.sql(
        f"""
        SELECT
            document_id,
            page_start,
            passage_order,
            detected_language,
            length(passage_text) AS chars,
            left(passage_text, 300) AS passage_preview
        FROM {ANALYSIS_PASSAGE_TABLE}
        WHERE analysis_id = '{analysis_id}'
        ORDER BY document_id, passage_order
        """
    )
)
