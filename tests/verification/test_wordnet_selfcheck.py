"""Regression tests: the corpora-missing state must fail loudly, never silently.

Simulates the Render failure mode from the diagnostic session (wordnet
download never ran) and asserts the self-check reports failure with an
ERROR-level log instead of passing quietly.
"""

import logging

import backend.verification.lexical_expansion as lex


def test_check_wordnet_ok_when_corpora_present():
    status = lex.check_wordnet()
    assert status.available is True
    assert status.detail


def test_check_wordnet_missing_returns_failure_loudly(monkeypatch, caplog):
    def _missing():
        raise LookupError("simulated missing corpora (nltk_data not downloaded)")

    monkeypatch.setattr(lex, "_probe_wordnet", _missing)
    with caplog.at_level(logging.DEBUG):
        status = lex.check_wordnet()
    assert status.available is False
    assert "simulated missing corpora" in status.detail
    error_records = [r for r in caplog.records if r.levelno >= logging.ERROR]
    assert error_records, "expected an ERROR-level log on missing corpora"
    assert any("WORDNET CORPORA MISSING" in r.message for r in error_records)


def test_check_wordnet_empty_returns_failure(monkeypatch):
    monkeypatch.setattr(lex, "_probe_wordnet", lambda: 0)
    status = lex.check_wordnet()
    assert status.available is False
    assert "zero synsets" in status.detail


def test_check_wordnet_never_raises(monkeypatch):
    monkeypatch.setattr(lex, "_probe_wordnet", lambda: 1 / 0)
    status = lex.check_wordnet()  # ZeroDivisionError inside probe
    assert status.available is False
