from scripts.build_databricks_app_bundle import build_bundle


def test_operational_refinement_materializes_expected_app(tmp_path):
    output = build_bundle(tmp_path / "databricks_app")
    source = (output / "app.py").read_text(encoding="utf-8")
    yaml_text = (output / "app.yaml").read_text(encoding="utf-8")

    assert 'st.markdown("### Analysis summary")' not in source
    assert 'st.markdown("### Brief analysis summary")' in source

    assert 'GPT20_DAILY_QUESTION_LIMIT = int(os.getenv("GPT20_DAILY_QUESTION_LIMIT", "30"))' in source
    assert 'LLAMA_DAILY_QUESTION_LIMIT = int(os.getenv("LLAMA_DAILY_QUESTION_LIMIT", "10"))' in source
    assert "def get_gpt20_daily_usage():" in source
    assert "def reserve_class_d_question_usage(model_selection):" in source
    assert "GPT-OSS 20B Ask questions remaining today" in source
    assert "Llama 3.3 70B Ask questions remaining today" in source
    assert 'name: GPT20_DAILY_QUESTION_LIMIT' in yaml_text
    assert 'value: "30"' in yaml_text
    assert 'name: LLAMA_DAILY_QUESTION_LIMIT' in yaml_text
    assert 'value: "10"' in yaml_text

    assert "Related to active analysis only" in source
    assert "Triage signal" in source
    assert "headline-derived screening signal" in source.lower()
    assert "Search scope: all processed MAIRA INVESTIGATION / MAIN_REPORT passages" in source
    assert "MAIRA search coverage:" in source
    assert "Deterministic weighted score:" in source

    manifest = (output / "ikf_bundle_manifest.json").read_text(encoding="utf-8")
    assert '"bundle_contract": "IKF_DATABRICKS_APP_BUNDLE_V0.12"' in manifest
    assert '"operational_refinement_version": "IKF_APP_OPERATIONAL_REFINEMENT_V0.2"' in manifest
    assert '"similarity_refinement_version": "IKF_APP_SIMILARITY_REFINEMENT_V0.1"' in manifest
