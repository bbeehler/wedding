from datetime import datetime, timezone
from urllib.parse import parse_qs, urlsplit
import pytest
from domain import invitation_url, csv_bytes, responses_open, clashes

def test_invitation_replaces_existing_query_and_fragment():
    url=invitation_url('https://wedding.streamlit.app/?old=1#section','a b&c')
    assert parse_qs(urlsplit(url).query)=={'invite':['a b&c']}
    assert not urlsplit(url).fragment

@pytest.mark.parametrize('url',['http://example.com','javascript:alert(1)','https://user:pass@example.com',''])
def test_invitation_requires_public_https(url):
    with pytest.raises(ValueError): invitation_url(url,'abc')

def test_csv_protects_formula_cells_and_quotes_commas():
    value=csv_bytes([{'Guest':'=HYPERLINK("evil")','Allergies':'Nuts, eggs'}]).decode('utf-8-sig')
    assert "'=HYPERLINK" in value and '"Nuts, eggs"' in value

def test_deadline_uses_timezone():
    settings={'response_deadline':'2027-04-30T23:59:00-04:00'}
    assert responses_open(settings,datetime(2027,5,1,3,58,tzinfo=timezone.utc))
    assert not responses_open(settings,datetime(2027,5,1,4,0,tzinfo=timezone.utc))

def test_adjacent_slots_are_not_conflicts():
    a={'day':'2027-05-28','owner':'Brian','start_time':'10:00','end_time':'11:00'}
    b={**a,'start_time':'11:00','end_time':'12:00'}
    assert not clashes([a,b],'day')
    b['start_time']='10:30'
    assert clashes([a,b],'day')
