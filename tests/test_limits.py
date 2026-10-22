from geolens.engine import evaluate
from test_decision import venue,hours


def test_duration_cannot_extend_past_explicit_user_end():
    result=evaluate([venue()],hours(),'tennis',{'duration_minutes':120,'end':'2026-10-23T09:00:00+05:30'})
    assert result[0]['eligibility']=='excluded'
    assert 'outside_requested_window' in result[0]['warning_codes']


def test_uncertain_access_and_green_are_not_claimed_verified():
    result=evaluate([venue()],hours()[:1],'tennis',{})[0]
    assert 'public_access_unverified' in result['limitations']
    assert result['score_high']>=result['score_low']
