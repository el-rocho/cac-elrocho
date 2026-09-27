from app.services.llm_service import generate_mock_extraction


def _measurements_for(text: str) -> dict[str, str]:
    preview = generate_mock_extraction(text, temp_id="regex-test")
    return {measurement.codigo: measurement.valor for measurement in preview.mediciones}


def test_regex_fallback_extracts_columnar_electrolytes_and_urine_results():
    measurements = _measurements_for(
        """
        Sodio                                                     142   mEq/l  (136 - 145)
        Potasio                                                    4.38  mEq/l  (3.5 - 5.1)
        Gamma-GT                                                   13    UN     (Inf. 60)
        Acido Urico                                                6.3   mg/dl (3.4 - 7.0)
        SISTEMÁTICO DE ORINA
        Proteínas                                                  NEGATIVO
        Glucosa                                                    NEGATIVO
        """
    )

    assert measurements["SODIO"] == "142"
    assert measurements["POTASIO"] == "4.38"
    assert measurements["GGT"] == "13"
    assert measurements["URIC_ACID"] == "6.3"
    assert measurements["PROTEIN_URINE"] == "NEGATIVO"
    assert measurements["GLUCOSE_URINE"] == "NEGATIVO"


def test_regex_fallback_does_not_take_reference_or_ratio_as_result():
    measurements = _measurements_for(
        """
        Bilirrubina total < 1.2 mg/dl
        PSA Total     0.672 ng/ml (Inf. 4)
        PSA Libre/PSA Total 44.64 %
        VCM: 9149 80 - 96
        """
    )

    assert "BILIRRUBINA_TOTAL" not in measurements
    assert measurements["PSA_TOTAL"] == "0.672"
    assert "VCM" not in measurements


def test_regex_fallback_handles_recoletas_specialty_sections():
    measurements = _measurements_for(
        """
        Hemoglobina A1c (NGSP)                                   5.4  %  (Inf. 5.7)
        Proteina C reactiva de amplio rango (wrPCR)               0.04 mg/dL (Inf. 0.50)
        Vitamina D 25-Hidroxi                                    23.72 ng/mL (Inf. 19)
        Velocidad de sedimentacion
        A la hora                                                   7  mm/h (Inf. 10)
        MARCADORES TUMORALES
        PSA                                                        0.725 ng/ml (Inf. 4)
        PSA Libre                                                  0.458 ng/ml
        PSA Libre/PSA Total                                       63.17 %
        """
    )

    assert measurements["HBA1C"] == "5.4"
    assert measurements["PROTEINA_C_REACTIVA"] == "0.04"
    assert measurements["VITAMIN_D"] == "23.72"
    assert measurements["VSG_1H"] == "7"
    assert measurements["PSA_TOTAL"] == "0.725"


def test_regex_fallback_handles_direct_biochemistry_and_tumor_markers():
    measurements = _measurements_for(
        """
        BUN(Nitrógeno Ureico)                                    21.5 mg/dL (7.0 - 21.0)
        Colesterol                                                167 mg/dL < 200 mg/dL
        HDL-Colesterol                                             59 mg/dL > 40 mg/dL
        CEA -Antígeno Carcinoembrionario                         0.866 ng/mL < 5 ng/mL
        CA 19-9                                                  3.03 UI/mL < 37 UI/mL
        """
    )

    assert measurements["BUN"] == "21.5"
    assert measurements["CHOLESTEROL_TOTAL"] == "167"
    assert measurements["CEA"] == "0.866"
    assert measurements["CA_19_9"] == "3.03"


def test_regex_fallback_rejects_reference_and_ocr_artifacts():
    measurements = _measurements_for(
        """
        Albúmina-prot.: Negativo
        HDL-Colesterol > 40 mg/dL Determinación no realizada
        VPM: 142 7 - 13
        Proteínas Totales 99.4 g/dL
        """
    )

    assert "ALBUMINA_SERICA" not in measurements
    assert "HDL" not in measurements
    assert "VPM" not in measurements
    assert "PROTEINAS_TOTALES" not in measurements
