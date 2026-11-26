"""Unit tests for T-HTN (modes M1_taxonomy / M3_evidence) in src/phase1_cf_audit.py.

Run: python -m pytest tests/test_taxonomy.py -q
"""
import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from phase1_cf_audit import THTN, query_ranges  # noqa: E402

FEATS = ["age", "female", "race_1", "race_2", "race_3", "race_4", "race_6", "race_7", "education", "income_pir",
         "insured", "routine_place", "visits_past_year", "diabetes_told", "high_chol_told", "current_smoker",
         "drinks_per_day", "vigorous_rec_pa", "moderate_rec_pa", "bmi", "waist", "total_chol", "hba1c",
         "self_rated_health"]
LO = pd.Series({f: 0.0 for f in FEATS} | {"bmi": 14.0, "waist": 55.0, "total_chol": 80.0, "hba1c": 3.5,
                                          "drinks_per_day": 0.0, "visits_past_year": 0.0, "education": 1.0,
                                          "self_rated_health": 1.0, "age": 20.0})
HI = pd.Series({f: 1.0 for f in FEATS} | {"bmi": 80.0, "waist": 180.0, "total_chol": 450.0, "hba1c": 16.0,
                                          "drinks_per_day": 25.0, "visits_past_year": 8.0, "education": 5.0,
                                          "self_rated_health": 5.0, "age": 80.0, "income_pir": 5.0})
FROZEN_ALWAYS = [f for f in FEATS if f not in THTN]


def query(**kw):
    base = {f: 0.0 for f in FEATS} | {"age": 55.0, "race_3": 1.0, "education": 3.0, "income_pir": 2.0,
                                      "visits_past_year": 3.0, "bmi": 22.0, "waist": 80.0, "total_chol": 200.0,
                                      "hba1c": 5.6, "self_rated_health": 3.0, "drinks_per_day": 0.0}
    base.update(kw)
    return pd.DataFrame([base])


def rng(q, mode="M1_taxonomy", missing=()):
    vary, pr = query_ranges(q, mode, FEATS, LO, HI, {}, missing=missing)
    return vary, pr


def asian(**kw):
    return query(race_3=0.0, race_6=1.0, **kw)


# ---- BMI edge cases (reviewer table) ----
@pytest.mark.parametrize("q,m1,m3", [
    (asian(bmi=22.0), None, None),
    (asian(bmi=23.0), None, None),
    (asian(bmi=24.0), (23.0, 24.0), (23.0, 24.0)),
    (asian(bmi=30.0), (23.0, 30.0), (28.5, 30.0)),
    (query(bmi=24.0), None, None),
    (query(bmi=30.0), (25.0, 30.0), (28.5, 30.0)),
])
def test_bmi(q, m1, m3):
    for mode, exp in (("M1_taxonomy", m1), ("M3_evidence", m3)):
        vary, pr = rng(q, mode)
        if exp is None:
            assert "bmi" not in vary
        else:
            assert pr["bmi"] == pytest.approx(list(exp))


# ---- waist edge cases ----
@pytest.mark.parametrize("q,m1,m3", [
    (query(female=0.0, waist=100.0), None, None),
    (query(female=0.0, waist=110.0), (102.0, 110.0), (104.5, 110.0)),
    (query(female=1.0, waist=90.0), (88.0, 90.0), (88.0, 90.0)),
    (query(female=1.0, waist=88.0), None, None),
])
def test_waist(q, m1, m3):
    for mode, exp in (("M1_taxonomy", m1), ("M3_evidence", m3)):
        vary, pr = rng(q, mode)
        if exp is None:
            assert "waist" not in vary
        else:
            assert pr["waist"] == pytest.approx(list(exp))


# ---- imputed values frozen in M1/M3 only ----
def test_imputed_frozen_in_thtn_only():
    q = query(bmi=31.0, waist=110.0, drinks_per_day=4.0, current_smoker=1.0)
    for mode in ("M1_taxonomy", "M3_evidence"):
        vary, _ = rng(q, mode, missing={"bmi", "waist", "drinks_per_day"})
        assert "bmi" not in vary and "waist" not in vary and "drinks_per_day" not in vary
        assert "current_smoker" in vary
    for mode in ("M0_global",):
        vary, _ = rng(q, mode, missing={"bmi", "waist", "drinks_per_day"})
        assert "bmi" in vary and "drinks_per_day" in vary


# ---- alcohol floor ----
@pytest.mark.parametrize("x,exp", [(0.0, None), (1.0, None), (2.0, (1.0, 2.0)), (6.0, (1.0, 6.0))])
def test_alcohol(x, exp):
    vary, pr = rng(query(drinks_per_day=x))
    if exp is None:
        assert "drinks_per_day" not in vary
    else:
        assert pr["drinks_per_day"] == pytest.approx(list(exp))


# ---- binary directions ----
def test_binary_directions():
    vary, pr = rng(query(insured=0.0, routine_place=0.0, current_smoker=1.0, moderate_rec_pa=0.0, vigorous_rec_pa=0.0))
    assert pr["insured"] == [0.0, 1.0] and pr["routine_place"] == [0.0, 1.0]
    assert pr["current_smoker"] == [0.0, 1.0]           # may go 1 -> 0 only (upper bound = query value)
    assert pr["moderate_rec_pa"] == [0.0, 1.0] and pr["vigorous_rec_pa"] == [0.0, 1.0]
    vary, _ = rng(query(insured=1.0, routine_place=1.0, current_smoker=0.0, moderate_rec_pa=1.0, vigorous_rec_pa=1.0))
    for f in ("insured", "routine_place", "current_smoker", "moderate_rec_pa", "vigorous_rec_pa"):
        assert f not in vary


# ---- everything outside the 8 features is always frozen ----
def test_frozen_features():
    q = query(insured=0.0, current_smoker=1.0, drinks_per_day=5.0, bmi=33.0, waist=115.0,
              total_chol=280.0, hba1c=6.3, self_rated_health=5.0, education=1.0, income_pir=0.5,
              visits_past_year=1.0, diabetes_told=1.0, high_chol_told=1.0)
    for mode in ("M1_taxonomy", "M3_evidence"):
        vary, pr = rng(q, mode)
        assert not set(vary) & set(FROZEN_ALWAYS)
        assert set(vary) <= set(THTN)
        for f, (a, b) in pr.items():                      # inside the training range
            assert LO[f] - 1e-9 <= a <= b <= HI[f] + 1e-9

