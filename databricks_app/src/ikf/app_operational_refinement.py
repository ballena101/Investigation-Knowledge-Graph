"""Final operational refinements for the Safety Investigation AI Sandbox.

This deterministic layer is intentionally applied after the other App adoptions.
It keeps product-facing cleanup, Class-D Ask quotas, Similar Cases wording and
News triage refinements separate from the core investigation/governance logic.
"""

from __future__ import annotations

import re


OPERATIONAL_REFINEMENT_VERSION = "IKF_APP_OPERATIONAL_REFINEMENT_V0.1"


def _replace_once(source: str, old: str, new: str, name: str) -> str:
    count = source.count(old)
    if count != 1:
        raise RuntimeError(
            f"Operational refinement failed at {name}: expected one match, found {count}."
        )
    return source.replace(old, new, 1)


def _remove_analysis_summary(source: str) -> str:
    start_marker = '\n    st.divider()\n    st.markdown("### Analysis summary")\n'
    end_marker = '\n@st.fragment\ndef render_compare_llms():\n'
    start = source.find(start_marker)
    end = source.find(end_marker, start)
    if start < 0 or end < 0:
        raise RuntimeError("Could not locate Analyse Documents summary block.")
    return source[:start] + "\n" + source[end:]


def _apply_question_quota_refinement(source: str) -> str:
    source = _replace_once(
        source,
        'LLAMA_DAILY_QUESTION_LIMIT = int(os.getenv("LLAMA_DAILY_QUESTION_LIMIT", "5"))',
        'GPT20_DAILY_QUESTION_LIMIT = int(os.getenv("GPT20_DAILY_QUESTION_LIMIT", "30"))\n'
        'LLAMA_DAILY_QUESTION_LIMIT = int(os.getenv("LLAMA_DAILY_QUESTION_LIMIT", "10"))',
        "Class-D quota defaults",
    )

    gpt_helper = '''def get_gpt20_daily_usage():
    user_key = get_current_user_key()
    usage_key = f"{user_key}|GPT20|{quota_date()}"

    query = """
    MERGE (u:ModelDailyUsage {usage_key: $usage_key})
    ON CREATE SET
        u.user_key = $user_key,
        u.model_key = 'GPT20',
        u.usage_date = $usage_date,
        u.question_count = 0,
        u.created_at = datetime()
    RETURN u.question_count AS question_count
    """

    with get_driver().session() as session:
        record = session.run(
            query,
            usage_key=usage_key,
            user_key=user_key,
            usage_date=quota_date(),
        ).single()

    return int(record["question_count"] or 0)


'''
    source = _replace_once(
        source,
        "def get_llama_daily_usage():\n",
        gpt_helper + "def get_llama_daily_usage():\n",
        "GPT-OSS daily usage helper",
    )

    reservation_helper = '''def reserve_class_d_question_usage(model_selection):
    """Atomically reserve per-user Ask allowances for the selected Class-D model(s)."""

    plans = []
    if model_selection in {"GPT20", "BOTH"}:
        plans.append(("GPT20", GPT20_DAILY_QUESTION_LIMIT))
    if model_selection in {"LLAMA70", "BOTH"}:
        plans.append(("LLAMA70", LLAMA_DAILY_QUESTION_LIMIT))

    if not plans:
        return {}

    user_key = get_current_user_key()
    usage_date = quota_date()

    def _reserve(tx):
        counts = {}
        for model_key, limit in plans:
            usage_key = f"{user_key}|{model_key}|{usage_date}"
            record = tx.run(
                """
                MERGE (u:ModelDailyUsage {usage_key: $usage_key})
                ON CREATE SET
                    u.user_key = $user_key,
                    u.model_key = $model_key,
                    u.usage_date = $usage_date,
                    u.question_count = 0,
                    u.created_at = datetime()
                WITH u
                WHERE u.question_count < $limit
                SET
                    u.question_count = u.question_count + 1,
                    u.updated_at = datetime()
                RETURN u.question_count AS question_count
                """,
                usage_key=usage_key,
                user_key=user_key,
                model_key=model_key,
                usage_date=usage_date,
                limit=limit,
            ).single()
            if record is None:
                raise RuntimeError(
                    f"The daily {model_key} Ask allowance has been reached."
                )
            counts[model_key] = int(record["question_count"] or 0)
        return counts

    with get_driver().session() as session:
        return session.execute_write(_reserve)


'''
    source = _replace_once(
        source,
        "def list_llama_daily_usage():\n",
        reservation_helper + "def list_llama_daily_usage():\n",
        "atomic Class-D Ask reservation",
    )

    # Ask quotas are for free-text Ask interactions, not for creating/running an analysis.
    form_marker = '    with st.form(\n        "new_analysis_form",\n'
    form_pos = source.find(form_marker)
    quota_pos = source.rfind("            llama_used = get_llama_daily_usage()\n", 0, form_pos)
    if quota_pos < 0 or form_pos < 0 or quota_pos >= form_pos:
        raise RuntimeError("Could not remove Analyse Documents Llama quota display.")
    source = source[:quota_pos] + source[form_pos:]

    analysis_guard_pattern = re.compile(
        r'\n            if \(\n'
        r'                needs_llama70\n'
        r'                and get_llama_daily_usage\(\)\n'
        r'                >= LLAMA_DAILY_QUESTION_LIMIT\n'
        r'            \):\n'
        r'                errors\.append\(\n'
        r'                    "The daily Llama 3\.3 70B question limit has been reached\."\n'
        r'                \)\n'
    )
    source, count = analysis_guard_pattern.subn("\n", source, count=1)
    if count != 1:
        raise RuntimeError("Could not remove analysis-time Llama quota guard.")

    analysis_consume_pattern = re.compile(
        r'\n                    if class_d_model_selection in \{\n'
        r'                        "LLAMA70",\n'
        r'                        "BOTH",\n'
        r'                    \}:\n'
        r'                        new_count = \(\n'
        r'                            consume_llama_daily_usage\(\)\n'
        r'                        \)\n'
        r'                        if new_count is None:\n'
        r'                            raise RuntimeError\(\n'
        r'                                "The Llama daily quota was reached before "\n'
        r'                                "the analysis could start\."\n'
        r'                            \)\n'
    )
    source, count = analysis_consume_pattern.subn("\n", source, count=1)
    if count != 1:
        raise RuntimeError("Could not remove analysis-time Llama quota consumption.")

    ask_display_pattern = re.compile(
        r'                if ask_model_selection in \{\n'
        r'                    "LLAMA70",\n'
        r'                    "BOTH",\n'
        r'                \}:\n'
        r'                    llama_used = get_llama_daily_usage\(\)\n'
        r'                    llama_remaining = max\(\n'
        r'                        LLAMA_DAILY_QUESTION_LIMIT\n'
        r'                        - llama_used,\n'
        r'                        0,\n'
        r'                    \)\n'
        r'                    st\.caption\(\n'
        r'                        "Llama 3\.3 70B questions remaining today: "\n'
        r'                        f"\{llama_remaining\}"\n'
        r'                    \)\n'
    )
    ask_display = '''                if ask_model_selection in {"GPT20", "BOTH"}:
                    gpt20_remaining = max(
                        GPT20_DAILY_QUESTION_LIMIT - get_gpt20_daily_usage(),
                        0,
                    )
                    st.caption(
                        "GPT-OSS 20B Ask questions remaining today: "
                        f"{gpt20_remaining} / {GPT20_DAILY_QUESTION_LIMIT}"
                    )

                if ask_model_selection in {"LLAMA70", "BOTH"}:
                    llama_remaining = max(
                        LLAMA_DAILY_QUESTION_LIMIT - get_llama_daily_usage(),
                        0,
                    )
                    st.caption(
                        "Llama 3.3 70B Ask questions remaining today: "
                        f"{llama_remaining} / {LLAMA_DAILY_QUESTION_LIMIT}"
                    )
'''
    source, count = ask_display_pattern.subn(ask_display, source, count=1)
    if count != 1:
        raise RuntimeError("Could not update Ask LLMs quota display.")

    ask_guard_pattern = re.compile(
        r'                if class_for_ask == "D":\n'
        r'                    if \(\n'
        r'                        ask_model_selection\n'
        r'                        in \{"LLAMA70", "BOTH"\}\n'
        r'                        and get_llama_daily_usage\(\)\n'
        r'                        >= LLAMA_DAILY_QUESTION_LIMIT\n'
        r'                    \):\n'
        r'                        ask_errors\.append\(\n'
        r'                            "The daily Llama 3\.3 70B question limit has been reached\."\n'
        r'                        \)\n'
    )
    ask_guard = '''                if class_for_ask == "D":
                    if (
                        ask_model_selection in {"GPT20", "BOTH"}
                        and get_gpt20_daily_usage() >= GPT20_DAILY_QUESTION_LIMIT
                    ):
                        ask_errors.append(
                            "The daily GPT-OSS 20B Ask limit has been reached."
                        )
                    if (
                        ask_model_selection in {"LLAMA70", "BOTH"}
                        and get_llama_daily_usage() >= LLAMA_DAILY_QUESTION_LIMIT
                    ):
                        ask_errors.append(
                            "The daily Llama 3.3 70B Ask limit has been reached."
                        )
'''
    source, count = ask_guard_pattern.subn(ask_guard, source, count=1)
    if count != 1:
        raise RuntimeError("Could not update Ask LLMs quota guards.")

    ask_consume_pattern = re.compile(
        r'                        if \(\n'
        r'                            class_for_ask == "D"\n'
        r'                            and ask_model_selection\n'
        r'                            in \{"LLAMA70", "BOTH"\}\n'
        r'                        \):\n'
        r'                            consumed = consume_llama_daily_usage\(\)\n'
        r'                            if consumed is None:\n'
        r'                                raise RuntimeError\(\n'
        r'                                    "The Llama daily quota could not be reserved\."\n'
        r'                                \)\n'
    )
    ask_consume = '''                        if class_for_ask == "D":
                            reserve_class_d_question_usage(
                                ask_model_selection
                            )
'''
    source, count = ask_consume_pattern.subn(ask_consume, source, count=1)
    if count != 1:
        raise RuntimeError("Could not replace Ask LLMs quota reservation.")

    return source


def _apply_news_refinement(source: str) -> str:
    sql_start = source.find('_NEWS_ALERTS_SQL = r"""')
    sql_end = source.find('\n"""', sql_start + 25)
    if sql_start < 0 or sql_end < 0:
        raise RuntimeError("Could not locate News SQL block.")

    sql = source[sql_start:sql_end]
    sql = sql.replace("THEN 'Fatal'", "THEN 'Fatality signal'", 1)
    sql = sql.replace("THEN 'Very Serious Casualty'", "THEN 'Injury signal'", 1)
    sql = sql.replace("THEN 'Very Serious Casualty'", "THEN 'Occurrence signal'", 3)
    source = source[:sql_start] + sql + source[sql_end:]

    source = _replace_once(
        source,
        'with tab_news:\n    st.subheader("News & Alerts")\n',
        'with tab_news:\n    st.subheader("News & Alerts")\n'
        '    st.caption(\n'
        '        "External alert intelligence. Event type and triage signals are derived "\n'
        '        "from alert text for screening only; they are not an official casualty "\n'
        '        "classification or validated investigation evidence."\n'
        '    )\n',
        "News triage disclaimer",
    )

    apply_filters_marker = '''            # Apply filters
            _filtered = _news_df.copy()
'''
    extra_filters = '''            _fcol3, _fcol4, _fcol5 = st.columns(3)
            with _fcol3:
                _sel_event_types = st.multiselect(
                    "Event type",
                    options=sorted(_news_df["eventtype"].dropna().unique().tolist()),
                    default=[],
                    placeholder="All event types",
                    key="news_event_type_filter",
                )
            with _fcol4:
                _sel_vessel_types = st.multiselect(
                    "Vessel type",
                    options=sorted(_news_df["vesseltype"].dropna().unique().tolist()),
                    default=[],
                    placeholder="All vessel types",
                    key="news_vessel_type_filter",
                )
            with _fcol5:
                _sel_match_reasons = st.multiselect(
                    "Matched by",
                    options=sorted(_news_df["match_reason"].dropna().unique().tolist()),
                    default=[],
                    placeholder="All match reasons",
                    key="news_match_reason_filter",
                )

            _news_text_search = st.text_input(
                "Search alert text",
                placeholder="e.g. engine fire, grounding, collision",
                key="news_text_filter",
            )

''' + apply_filters_marker
    source = _replace_once(
        source,
        apply_filters_marker,
        extra_filters,
        "News filters",
    )

    date_filter = '''            if isinstance(_date_range, tuple) and len(_date_range) == 2:
                _d_start, _d_end = _date_range
                _filtered = _filtered[
                    (_filtered["alert_timestamp"].dt.date >= _d_start)
                    & (_filtered["alert_timestamp"].dt.date <= _d_end)
                ]
'''
    date_filter_plus = date_filter + '''            if _sel_event_types:
                _filtered = _filtered[
                    _filtered["eventtype"].isin(_sel_event_types)
                ]
            if _sel_vessel_types:
                _filtered = _filtered[
                    _filtered["vesseltype"].isin(_sel_vessel_types)
                ]
            if _sel_match_reasons:
                _filtered = _filtered[
                    _filtered["match_reason"].isin(_sel_match_reasons)
                ]
            if _news_text_search.strip():
                _needle = _news_text_search.strip().casefold()
                _filtered = _filtered[
                    _filtered["headlinefull"].fillna("").str.casefold().str.contains(
                        _needle,
                        regex=False,
                    )
                ]

            _case_phrases = []
            _case_terms = set()
            if active_analysis_id:
                try:
                    _case_graph = load_analysis_graph(active_analysis_id)
                    _case_stopwords = {
                        "with", "from", "that", "this", "were", "into", "after",
                        "before", "during", "vessel", "ship", "event", "finding",
                        "factor", "safety", "system",
                    }
                    for _node in _case_graph.get("nodes") or []:
                        if _node.get("node_kind") not in {
                            "Event", "ContributingFactor", "SafetyIssue", "Finding", "System"
                        }:
                            continue
                        _label = str(_node.get("label") or "").strip().casefold()
                        if not _label or _label == "subject vessel":
                            continue
                        _case_phrases.append(_label)
                        for _word in _label.replace("-", " ").replace("/", " ").split():
                            _word = _word.strip(".,:;()[]{}")
                            if len(_word) >= 4 and _word not in _case_stopwords:
                                _case_terms.add(_word)
                except Exception:
                    _case_phrases = []
                    _case_terms = set()

            if _case_phrases or _case_terms:
                def _news_case_relevance(value):
                    _text = str(value or "").casefold()
                    _phrase_score = 3 * sum(
                        1 for _phrase in _case_phrases if _phrase in _text
                    )
                    _term_score = sum(
                        1 for _term in _case_terms if _term in _text
                    )
                    return _phrase_score + _term_score

                _filtered = _filtered.copy()
                _filtered["_case_relevance"] = _filtered["headlinefull"].apply(
                    _news_case_relevance
                )
                _related_only = st.checkbox(
                    "Related to active analysis only",
                    value=False,
                    key="news_related_to_active_analysis",
                    help=(
                        "Deterministic lexical relevance to the active analysis graph. "
                        "This is an external intelligence aid, not evidence linking the alert to the case."
                    ),
                )
                if _related_only:
                    _filtered = _filtered[_filtered["_case_relevance"] > 0]
                st.caption(
                    "Active-case relevance uses only existing analysis concepts; no extra LLM call is made."
                )
'''
    source = _replace_once(
        source,
        date_filter,
        date_filter_plus,
        "News active-analysis relevance",
    )

    source = _replace_once(
        source,
        'int((_filtered["lossoflife"] == "Yes").sum())',
        'int(_filtered.loc[_filtered["lossoflife"] == "Yes", "alert_id"].nunique())',
        "unique fatal-alert KPI",
    )

    source = source.replace(
        '"Severity", "Match reason", "Event type",',
        '"Triage signal", "Match reason", "Event type",',
        1,
    )
    source = source.replace(
        '"Severity": st.column_config.TextColumn(\n                            "Severity", width="small",\n                        ),',
        '"Triage signal": st.column_config.TextColumn(\n                            "Triage signal", width="small",\n                            help="Headline-derived screening signal; not an official casualty classification.",\n                        ),',
        1,
    )

    return source


def _apply_similar_cases_refinement(source: str) -> str:
    source = _replace_once(
        source,
        '            "Deterministic lexical retrieval from processed case concepts. "\n'
        '            "No embedding or LLM similarity score is used."',
        '            "Search scope: all processed MAIRA INVESTIGATION / MAIN_REPORT passages "\n'
        '            "with canonical passages; the current report package is excluded. "\n'
        '            "Matching is deterministic and lexical over existing case concepts. "\n'
        '            "No embedding or LLM similarity score is used at this stage."',
        "Similar Cases corpus explanation",
    )

    source = _replace_once(
        source,
        '            "External/news similarity remains separate from validated "\n'
        '            "investigation knowledge and is handled in the News/dashboard "\n'
        '            "workstream."',
        '            "Recent alerts remain external, unverified intelligence. In News & Alerts, "\n'
        '            "use ‘Related to active analysis only’ to apply a deterministic lexical "\n'
        '            "screen against the active analysis concepts; this does not turn an alert "\n'
        '            "into investigation evidence."',
        "Similar Cases News guidance",
    )
    return source


def transform_app_operational_refinement(source: str) -> tuple[str, tuple[str, ...]]:
    applied = []

    source = _remove_analysis_summary(source)
    applied.append("analysis_summary_findings_only")

    source = _apply_question_quota_refinement(source)
    applied.append("class_d_ask_quotas_gpt20_30_llama70_10")
    applied.append("analysis_runs_do_not_consume_ask_quota")

    source = _apply_news_refinement(source)
    applied.append("news_triage_semantics_and_filters")
    applied.append("news_active_analysis_lexical_relevance")
    applied.append("news_unique_fatal_alert_count")

    source = _apply_similar_cases_refinement(source)
    applied.append("similar_cases_full_processed_maira_scope_wording")

    return source, tuple(applied)
