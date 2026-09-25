"""Final operational refinements for the Safety Investigation AI Sandbox."""

from __future__ import annotations

import re


OPERATIONAL_REFINEMENT_VERSION = "IKF_APP_OPERATIONAL_REFINEMENT_V0.2"


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
        "GPT-OSS usage helper",
    )

    reservation_helper = '''def reserve_class_d_question_usage(model_selection):
    """Reserve the selected Class-D Ask allowances in one Neo4j transaction."""
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
        "Class-D Ask reservation helper",
    )

    # Remove the analysis-page quota widget/admin controls. Ask allowances apply
    # only to free-text questions, not to analysis creation or analysis runs.
    form_marker = '    with st.form(\n        "new_analysis_form",\n'
    form_pos = source.find(form_marker)
    quota_pos = source.rfind("            llama_used = get_llama_daily_usage()\n", 0, form_pos)
    if quota_pos < 0 or form_pos < 0:
        raise RuntimeError("Could not locate Analyse Documents quota block.")
    source = source[:quota_pos] + source[form_pos:]

    analysis_guard = re.compile(
        r'\n            if \(\n'
        r'                needs_llama70\n'
        r'                and get_llama_daily_usage\(\)\n'
        r'                >= LLAMA_DAILY_QUESTION_LIMIT\n'
        r'            \):\n'
        r'                errors\.append\(\n'
        r'                    "The daily Llama 3\.3 70B question limit has been reached\."\n'
        r'                \)\n'
    )
    source, count = analysis_guard.subn("\n", source, count=1)
    if count != 1:
        raise RuntimeError("Could not remove analysis-time Llama quota guard.")

    analysis_consume = re.compile(
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
    source, count = analysis_consume.subn("\n", source, count=1)
    if count != 1:
        raise RuntimeError("Could not remove analysis-time quota consumption.")

    ask_display = re.compile(
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
    ask_display_new = '''                if ask_model_selection in {"GPT20", "BOTH"}:
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
    source, count = ask_display.subn(ask_display_new, source, count=1)
    if count != 1:
        raise RuntimeError("Could not update Ask quota display.")

    ask_guard = re.compile(
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
    ask_guard_new = '''                if class_for_ask == "D":
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
    source, count = ask_guard.subn(ask_guard_new, source, count=1)
    if count != 1:
        raise RuntimeError("Could not update Ask quota guards.")

    ask_consume = re.compile(
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
    source, count = ask_consume.subn(
        '''                        if class_for_ask == "D":
                            reserve_class_d_question_usage(
                                ask_model_selection
                            )
''',
        source,
        count=1,
    )
    if count != 1:
        raise RuntimeError("Could not replace Ask quota reservation.")

    return source


def _apply_news_refinement(source: str) -> str:
    # Keep the current governed data query but relabel headline-derived severity
    # values as triage signals rather than official casualty classifications.
    sql_start = source.find('_NEWS_ALERTS_SQL = r"""')
    sql_end = source.find('\n"""', sql_start + 25)
    if sql_start < 0 or sql_end < 0:
        raise RuntimeError("Could not locate News SQL block.")
    sql = source[sql_start:sql_end]
    sql = sql.replace("THEN 'Fatal'", "THEN 'Fatality signal'", 1)
    sql = sql.replace("THEN 'Very Serious Casualty'", "THEN 'Injury signal'", 1)
    sql = sql.replace("THEN 'Very Serious Casualty'", "THEN 'Occurrence signal'", 3)
    source = source[:sql_start] + sql + source[sql_end:]

    news_start = source.find("\nwith tab_news:\n")
    news_end = source.find("\nwith tab_transcriptions:\n", news_start)
    if news_start < 0 or news_end < 0:
        raise RuntimeError("Could not locate the materialized News tab.")

    news_tab = r'''
with tab_news:
    st.subheader("News & Alerts")
    st.caption(
        "External alert intelligence. Event type and triage signals are derived "
        "from alert text for screening only; they are not an official casualty "
        "classification or validated investigation evidence."
    )

    if not SQL_WAREHOUSE_ID:
        st.warning(
            "**SQL warehouse not configured.** Set the `SQL_WAREHOUSE_ID` "
            "environment variable in `app.yaml` to display live news data."
        )
        if NEWS_DASHBOARD_URL:
            st.link_button(
                "Open News & Alerts dashboard (fallback)",
                NEWS_DASHBOARD_URL,
                type="primary",
                use_container_width=True,
            )
    else:
        with st.spinner("Querying news alerts for the last 7 days…"):
            _news_df, _news_err = fetch_news_alerts_data()

        if _news_err:
            st.error(f"Failed to load news data: {_news_err}")
        elif _news_df is None or _news_df.empty:
            st.info("No alerts found for the last 7 days.")
        else:
            _filtered = _news_df.copy()

            _f1, _f2 = st.columns(2)
            with _f1:
                _countries = sorted(
                    _news_df["match_country"].dropna().unique().tolist()
                )
                _selected_countries = st.multiselect(
                    "Country affected",
                    options=_countries,
                    default=[],
                    placeholder="All countries",
                    key="news_country_filter",
                )
            with _f2:
                _min_date = _news_df["alert_timestamp"].dt.date.min()
                _max_date = _news_df["alert_timestamp"].dt.date.max()
                _date_range = st.date_input(
                    "Date range",
                    value=(_min_date, _max_date),
                    min_value=_min_date,
                    max_value=_max_date,
                    key="news_date_range",
                )

            _f3, _f4, _f5 = st.columns(3)
            with _f3:
                _event_types = st.multiselect(
                    "Event type",
                    options=sorted(_news_df["eventtype"].dropna().unique().tolist()),
                    default=[],
                    placeholder="All event types",
                    key="news_event_type_filter",
                )
            with _f4:
                _vessel_types = st.multiselect(
                    "Vessel type",
                    options=sorted(_news_df["vesseltype"].dropna().unique().tolist()),
                    default=[],
                    placeholder="All vessel types",
                    key="news_vessel_type_filter",
                )
            with _f5:
                _match_reasons = st.multiselect(
                    "Matched by",
                    options=sorted(_news_df["match_reason"].dropna().unique().tolist()),
                    default=[],
                    placeholder="All match reasons",
                    key="news_match_reason_filter",
                )

            _text_search = st.text_input(
                "Search alert text",
                placeholder="e.g. engine fire, grounding, collision",
                key="news_text_filter",
            )

            if _selected_countries:
                _filtered = _filtered[
                    _filtered["match_country"].isin(_selected_countries)
                ]
            if isinstance(_date_range, tuple) and len(_date_range) == 2:
                _start_date, _end_date = _date_range
                _filtered = _filtered[
                    (_filtered["alert_timestamp"].dt.date >= _start_date)
                    & (_filtered["alert_timestamp"].dt.date <= _end_date)
                ]
            if _event_types:
                _filtered = _filtered[_filtered["eventtype"].isin(_event_types)]
            if _vessel_types:
                _filtered = _filtered[_filtered["vesseltype"].isin(_vessel_types)]
            if _match_reasons:
                _filtered = _filtered[_filtered["match_reason"].isin(_match_reasons)]
            if _text_search.strip():
                _filtered = _filtered[
                    _filtered["headlinefull"].fillna("").str.contains(
                        _text_search.strip(),
                        case=False,
                        regex=False,
                    )
                ]

            _case_phrases = []
            _case_terms = set()
            if active_analysis_id:
                try:
                    _case_graph = load_analysis_graph(active_analysis_id)
                    _stop = {
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
                        for _term in re.findall(r"\w+", _label, flags=re.UNICODE):
                            if len(_term) >= 4 and _term not in _stop:
                                _case_terms.add(_term)
                except Exception:
                    _case_phrases = []
                    _case_terms = set()

            if _case_phrases or _case_terms:
                def _active_case_relevance(value):
                    _text = str(value or "").casefold()
                    return (
                        3 * sum(1 for _phrase in _case_phrases if _phrase in _text)
                        + sum(1 for _term in _case_terms if _term in _text)
                    )

                _filtered = _filtered.copy()
                _filtered["_case_relevance"] = _filtered["headlinefull"].apply(
                    _active_case_relevance
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
                    "Active-case relevance uses existing analysis concepts only; no extra LLM call is made."
                )

            if _filtered.empty:
                st.info("No alerts match the selected filters.")
            else:
                k1, k2, k3, k4 = st.columns(4)
                k1.metric("Total alerts", int(_filtered["alert_id"].nunique()))
                _last_update = _filtered["load_date"].max()
                k2.metric(
                    "Last update",
                    _last_update.strftime("%Y-%m-%d %H:%M") if pd.notna(_last_update) else "—",
                )
                k3.metric(
                    "Fatal incidents",
                    int(
                        _filtered.loc[
                            _filtered["lossoflife"] == "Yes",
                            "alert_id",
                        ].nunique()
                    ),
                )
                k4.metric(
                    "Countries",
                    int(_filtered["match_country"].dropna().nunique()),
                )

                st.markdown("#### Alert locations")
                _map_df = _filtered.dropna(
                    subset=["event_location_latitude", "event_location_longitude"]
                ).rename(
                    columns={
                        "event_location_latitude": "latitude",
                        "event_location_longitude": "longitude",
                    }
                )
                if not _map_df.empty:
                    st.map(_map_df[["latitude", "longitude"]])
                else:
                    st.caption("No geo-located alerts available.")

                st.markdown("#### Alert details")
                _detail_cols = [
                    "first_alert_timestamp", "alert_timestamp", "headlinefull",
                    "severity", "match_reason", "eventtype", "alert_version",
                ]
                _display_df = (
                    _filtered[_detail_cols]
                    .sort_values("alert_timestamp", ascending=False)
                    .reset_index(drop=True)
                )
                _display_df.columns = [
                    "First seen", "Latest update", "Headline",
                    "Triage signal", "Match reason", "Event type", "Version",
                ]
                st.dataframe(
                    _display_df,
                    column_config={
                        "Triage signal": st.column_config.TextColumn(
                            "Triage signal",
                            help=(
                                "Headline-derived screening signal; not an official "
                                "casualty classification."
                            ),
                        )
                    },
                    use_container_width=True,
                    height=400,
                )

                ch1, ch2 = st.columns(2)
                with ch1:
                    st.markdown("#### Alerts by vessel type")
                    _vtype = (
                        _filtered.drop_duplicates(subset=["alert_id", "vesseltype"])
                        .groupby("vesseltype")["alert_id"].nunique()
                        .sort_values(ascending=False).head(15)
                    )
                    if not _vtype.empty:
                        st.bar_chart(_vtype)
                with ch2:
                    st.markdown("#### Alerts by country")
                    _country = (
                        _filtered[_filtered["match_country"].notna()]
                        .drop_duplicates(subset=["alert_id", "match_country"])
                        .groupby("match_country")["alert_id"].nunique()
                        .sort_values(ascending=False).head(15)
                    )
                    if not _country.empty:
                        st.bar_chart(_country)

                ch3, ch4 = st.columns(2)
                with ch3:
                    st.markdown("#### Alerts by event type")
                    _etype = (
                        _filtered.drop_duplicates(subset=["alert_id", "eventtype"])
                        .groupby("eventtype")["alert_id"].nunique()
                        .sort_values(ascending=False)
                    )
                    if not _etype.empty:
                        st.bar_chart(_etype)
                with ch4:
                    st.markdown("#### Daily alert count")
                    _daily = (
                        _filtered.assign(day=_filtered["alert_timestamp"].dt.date)
                        .drop_duplicates(subset=["alert_id", "day"])
                        .groupby("day")["alert_id"].nunique().sort_index()
                    )
                    if not _daily.empty:
                        st.bar_chart(_daily)

    st.caption(
        "News remains external, unvalidated information and is not mixed with "
        "validated investigation findings."
    )
'''
    source = source[:news_start] + "\n" + news_tab + source[news_end:]
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
        '            "use ‘Related to active analysis only’ for deterministic lexical screening "\n'
        '            "against active-analysis concepts; this does not turn an alert into evidence."',
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
