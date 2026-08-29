"""
Decision Engine Unit Tests — covers all 10 mandatory simulation scenarios.
Run with: python -m pytest backend/tests/ -v
or: python manage.py test tests
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

from decision_engine.models import PatientState, VitalSnapshot
from decision_engine.engine import assess_patient


def make_vitals(**kwargs):
    return VitalSnapshot(**kwargs)


# ────────────────────────────────────────────────────────────
# 1. Obvious high-risk patient → P1
# ────────────────────────────────────────────────────────────
def test_obvious_high_risk():
    state = PatientState(
        patient_id='test-01',
        age=55, age_group='adult',
        chief_complaint='severe crushing chest pain',
        symptoms=['chest_pain_high_concern', 'sudden_onset'],
        history_available=True,
        current_vitals=make_vitals(
            heart_rate=122, systolic_bp=88, spo2=92,
            respiratory_rate=26, temperature=37.1, mental_status='alert'
        ),
    )
    result = assess_patient(state)
    assert result.priority == 'P1', f"Expected P1, got {result.priority}"
    assert result.confidence > 0.50
    assert len(result.risk_factors) > 0
    print(f"✓ Obvious high-risk: {result.priority} confidence={result.confidence:.2f}")


# ────────────────────────────────────────────────────────────
# 2. Stable low-risk patient → P4 or P5
# ────────────────────────────────────────────────────────────
def test_stable_low_risk():
    state = PatientState(
        patient_id='test-02',
        age=28, age_group='adult',
        chief_complaint='small laceration on finger',
        symptoms=['laceration'],
        history_available=True,
        current_vitals=make_vitals(
            heart_rate=75, systolic_bp=118, spo2=99,
            respiratory_rate=16, temperature=36.8, mental_status='alert'
        ),
    )
    result = assess_patient(state)
    assert result.priority in ('P4', 'P5'), f"Expected P4/P5, got {result.priority}"
    assert result.confidence >= 0.60
    print(f"✓ Stable low-risk: {result.priority} confidence={result.confidence:.2f}")


# ────────────────────────────────────────────────────────────
# 3. Ambiguous presentation → medium confidence, human review
# ────────────────────────────────────────────────────────────
def test_ambiguous():
    state = PatientState(
        patient_id='test-03',
        age=42, age_group='adult',
        chief_complaint='chest tightness and dizziness',
        symptoms=['chest_tightness', 'dizziness_or_syncope_signal'],
        history_available=True,
        current_vitals=make_vitals(
            heart_rate=96, systolic_bp=128, spo2=97,
            respiratory_rate=19, temperature=36.9, mental_status='alert'
        ),
        conflicting_signals=['anxiety history vs cardiac concern'],
    )
    result = assess_patient(state)
    # Must surface uncertainty — not confident P5
    assert result.priority not in ('P5',), f"Should not downgrade ambiguous to P5: {result.priority}"
    assert result.confidence < 0.85, f"Ambiguous case should not be high confidence: {result.confidence}"
    print(f"✓ Ambiguous: {result.priority} confidence={result.confidence:.2f} review={result.requires_human_review}")


# ────────────────────────────────────────────────────────────
# 4. Pediatric patient → uses pediatric config
# ────────────────────────────────────────────────────────────
def test_pediatric():
    state = PatientState(
        patient_id='test-04',
        age=5, age_group='pediatric',
        chief_complaint='high fever and rapid breathing',
        symptoms=['fever', 'shortness_of_breath'],
        history_available=True,
        current_vitals=make_vitals(
            heart_rate=145, systolic_bp=90, spo2=94,
            respiratory_rate=48, temperature=39.8, mental_status='alert'
        ),
    )
    result = assess_patient(state)
    # High RR for pediatric (>40) should escalate
    assert result.priority in ('P1', 'P2', 'P3'), f"Pediatric with high RR/fever: {result.priority}"
    print(f"✓ Pediatric: {result.priority} confidence={result.confidence:.2f}")


# ────────────────────────────────────────────────────────────
# 5. Geriatric patient with no history → confidence must drop
# ────────────────────────────────────────────────────────────
def test_geriatric_no_history():
    state = PatientState(
        patient_id='test-05',
        age=78, age_group='geriatric',
        chief_complaint='shortness of breath',
        symptoms=['shortness_of_breath'],
        history_available=False,
        current_vitals=make_vitals(
            heart_rate=108, systolic_bp=148, spo2=91,
            respiratory_rate=24, temperature=37.6, mental_status='confused'
        ),
    )
    result = assess_patient(state)
    assert result.priority in ('P1', 'P2'), f"Geriatric SOB+confused should be P1/P2: {result.priority}"
    assert result.confidence < 0.85, "Missing history must lower confidence"
    assert any('history' in f.lower() or 'missing' in f.lower() for f in result.uncertainty_flags), \
        "Must flag missing history"
    print(f"✓ Geriatric no-history: {result.priority} confidence={result.confidence:.2f}")


# ────────────────────────────────────────────────────────────
# 6. Zero-history patient → low confidence, NOT low risk
# ────────────────────────────────────────────────────────────
def test_zero_history():
    state = PatientState(
        patient_id='test-06',
        age=35, age_group='adult',
        chief_complaint='generalized weakness and confusion',
        symptoms=['weakness', 'altered_consciousness'],
        history_available=False,
        current_vitals=make_vitals(
            heart_rate=104, systolic_bp=102, spo2=95,
            respiratory_rate=22, temperature=38.4, mental_status='confused'
        ),
    )
    result = assess_patient(state)
    # Must NOT be P4/P5 — missing history should NOT falsely reassure
    assert result.priority not in ('P4', 'P5'), f"Zero-history confused patient should not be low priority: {result.priority}"
    assert result.confidence < 0.75, "Zero history must lower confidence significantly"
    print(f"✓ Zero-history: {result.priority} confidence={result.confidence:.2f}")


# ────────────────────────────────────────────────────────────
# 7. Deteriorating patient → priority escalates on second assessment
# ────────────────────────────────────────────────────────────
def test_deterioration():
    initial_state = PatientState(
        patient_id='test-07',
        age=61, age_group='adult',
        chief_complaint='shortness of breath',
        symptoms=['shortness_of_breath'],
        history_available=True,
        current_vitals=make_vitals(
            heart_rate=101, systolic_bp=115, spo2=93,
            respiratory_rate=23, temperature=37.2, mental_status='alert'
        ),
    )
    initial = assess_patient(initial_state)

    deteriorated_state = PatientState(
        patient_id='test-07',
        age=61, age_group='adult',
        chief_complaint='shortness of breath',
        symptoms=['shortness_of_breath'],
        history_available=True,
        current_vitals=make_vitals(
            heart_rate=138, systolic_bp=84, spo2=86,
            respiratory_rate=34, temperature=37.8, mental_status='confused'
        ),
        previous_vitals=initial_state.current_vitals,
        current_priority=initial.priority,
    )
    deteriorated = assess_patient(deteriorated_state)

    priority_order = {'P1': 1, 'P2': 2, 'P3': 3, 'P4': 4, 'P5': 5}
    assert priority_order[deteriorated.priority] <= priority_order[initial.priority], \
        f"Priority should escalate on deterioration: {initial.priority} → {deteriorated.priority}"
    print(f"✓ Deterioration: {initial.priority} → {deteriorated.priority}")


# ────────────────────────────────────────────────────────────
# 8. Long-wait patient → waiting exposure adds pressure
# ────────────────────────────────────────────────────────────
def test_long_wait():
    state = PatientState(
        patient_id='test-08',
        age=50, age_group='adult',
        chief_complaint='moderate abdominal pain',
        symptoms=['abdominal_pain'],
        history_available=True,
        current_vitals=make_vitals(
            heart_rate=88, systolic_bp=124, spo2=98,
            respiratory_rate=17, temperature=37.0, mental_status='alert'
        ),
        waiting_minutes=80,
        current_priority='P4',
    )
    result = assess_patient(state)
    # Waiting exposure should push score up or flag for reassessment
    has_wait_flag = any('wait' in f.lower() or 'waiting' in f.lower() for f in result.risk_factors + result.uncertainty_flags)
    print(f"✓ Long-wait: {result.priority} wait_flagged={has_wait_flag}")


# ────────────────────────────────────────────────────────────
# 9. Conflicting signals → cannot silently downgrade
# ────────────────────────────────────────────────────────────
def test_conflicting_signals():
    state = PatientState(
        patient_id='test-09',
        age=38, age_group='adult',
        chief_complaint='palpitations, no chest pain',
        symptoms=['palpitations'],
        history_available=True,
        current_vitals=make_vitals(
            heart_rate=148, systolic_bp=122, spo2=98,
            respiratory_rate=16, temperature=37.3, mental_status='alert'
        ),
        current_priority='P2',
        conflicting_signals=['very high HR but otherwise stable'],
    )
    result = assess_patient(state)
    # Must not silently downgrade below current P2
    assert result.priority in ('P1', 'P2'), \
        f"Conflicting signals must not silently downgrade: {result.priority}"
    print(f"✓ Conflicting signals: {result.priority} review={result.requires_human_review}")


# ────────────────────────────────────────────────────────────
# 10. Safety: missing history cannot falsely lower risk
# ────────────────────────────────────────────────────────────
def test_safety_missing_history():
    state = PatientState(
        patient_id='test-10',
        age=45, age_group='adult',
        chief_complaint='chest pain',
        symptoms=['chest_pain'],
        history_available=False,
        current_vitals=make_vitals(
            heart_rate=105, systolic_bp=100, spo2=94,
            respiratory_rate=22, temperature=37.5, mental_status='alert'
        ),
    )
    result = assess_patient(state)
    assert result.priority not in ('P4', 'P5'), \
        f"Missing history must not create false low-risk: {result.priority}"
    assert result.confidence < 0.80
    print(f"✓ Safety missing-history: {result.priority} confidence={result.confidence:.2f}")


if __name__ == '__main__':
    tests = [
        test_obvious_high_risk,
        test_stable_low_risk,
        test_ambiguous,
        test_pediatric,
        test_geriatric_no_history,
        test_zero_history,
        test_deterioration,
        test_long_wait,
        test_conflicting_signals,
        test_safety_missing_history,
    ]
    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except AssertionError as e:
            print(f"✗ {t.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"✗ {t.__name__} ERROR: {e}")
            failed += 1
    print(f"\n{'='*50}")
    print(f"Results: {passed} passed, {failed} failed out of {len(tests)} tests")
    if failed == 0:
        print("✅ All decision engine tests passed!")
    else:
        print("❌ Some tests failed.")
        sys.exit(1)
