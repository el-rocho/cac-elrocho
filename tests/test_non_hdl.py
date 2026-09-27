from app.services.analito_normalizer import normalize_analito
from app.services.metrics import calculate_ratios


def test_non_hdl_is_derived_from_total_cholesterol_and_hdl():
    derived = calculate_ratios({"CHOLESTEROL_TOTAL": 187.0, "HDL": 52.0})

    assert derived["NON_HDL"] == 135.0


def test_non_hdl_requires_both_lipid_measurements():
    assert "NON_HDL" not in calculate_ratios({"CHOLESTEROL_TOTAL": 187.0})
    assert "NON_HDL" not in calculate_ratios({"HDL": 52.0})


def test_normalizer_recognizes_an_explicit_non_hdl_measurement():
    code, name, category, unit = normalize_analito("Colesterol no-HDL")

    assert (code, name, category, unit) == (
        "NON_HDL", "Colesterol no-HDL", "bioquimica", "mg/dL"
    )
