"""Pruebas de los diagnósticos visibles al comprobar Gemini."""

from app.api.settings import _gemini_error_detail


def test_gemini_error_detail_preserves_provider_code_and_text():
    provider_message = "400 FAILED_PRECONDITION: API key not valid. Please pass a valid API key."

    assert _gemini_error_detail(RuntimeError(provider_message)) == provider_message


def test_gemini_error_detail_names_empty_timeout_exception():
    assert _gemini_error_detail(TimeoutError()) == "TimeoutError"
