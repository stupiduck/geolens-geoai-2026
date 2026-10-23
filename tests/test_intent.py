import pytest
from geolens.model import explicit_location, explicit_commute


@pytest.mark.parametrize('question,expected',[
    ('Where should I hike tomorrow morning near Lonavala, Maharashtra?', 'Lonavala, Maharashtra'),
    ('Suggest hiking near Lonavala and Khandala this weekend', 'Lonavala and Khandala'),
    ('Where can I run in Indiranagar, Bengaluru tomorrow morning?', 'Indiranagar, Bengaluru'),
    ('कल सुबह पवई, मुंबई में अस्थमा के साथ दौड़ना ठीक रहेगा?', 'पवई, मुंबई'),
    ('कल सुबह लोनावला में हाइकिंग कहाँ करूँ?', 'लोनावला'),
    ('कल सुबह पवई मुंबई के पास दौड़ने की जगह बताओ', 'पवई मुंबई'),
])
def test_compound_location_preserves_geographic_phrase(question,expected):
    assert explicit_location(question)==expected


def test_commute_is_not_mistaken_for_recreational_cycling():
    assert explicit_commute('Can I cycle to work tomorrow?')
    assert explicit_commute('कल साइकिल से दफ्तर जाना है')
    assert not explicit_commute('Where should I cycle tomorrow morning?')


def test_hindi_language_request_is_not_a_geographic_clause():
    assert explicit_location('हिंदी में बताइए') is None
    assert explicit_location('बारिश में दौड़ना ठीक होगा?') is None
