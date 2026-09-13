"""Smoke every planner page and the guest portal without network or real guest data."""
from pathlib import Path
from types import SimpleNamespace
from datetime import datetime, timezone
from streamlit.testing.v1 import AppTest

class Query:
    def __init__(self, records): self.records=records
    def select(self,*a,**kw): return self
    def order(self,*a,**kw): return self
    def range(self,*a,**kw): return self
    def execute(self): return SimpleNamespace(data=self.records)

class Fake:
    def __init__(self, planner=True):
        self.auth=SimpleNamespace(get_session=lambda:True,get_user=lambda:True)
        self.data={'planners':[{'user_id':'planner'}] if planner else [],
          'wedding_settings':[{'id':1,'title':'Angie & Brian','welcome_message':'Welcome','booking_instructions':'Instructions','contact_information':'','response_deadline':'2027-04-30T23:59:00-04:00'}],
          'guests':[{'id':'g1','full_name':'Test Guest','household':'Test','portal_email':'guest@example.invalid','invitation_code':'test-code','active':True,'is_child':False,'table_number':''}],
          'events':[{'id':'e1','title':'Reception','event_date':'2027-05-29','start_time':None,'end_time':None,'location':'Montebello','description':'Details','dress_code':'','published':True}],
          'event_invites':[{'id':'i1','guest_id':'g1','event_id':'e1'}]}
    def table(self,name): return Query(self.data.get(name,[]))

def start(planner=True):
    app=AppTest.from_file(str(Path(__file__).parents[1]/'app.py'))
    app.session_state.db=Fake(planner)
    app.session_state.user='test-user'
    app.run()
    assert not app.exception
    assert not app.error, [e.value for e in app.error]
    return app

def test_planner_pages_render():
    app=start()
    pages=app.sidebar.radio[0].options
    for page in pages:
        app.sidebar.radio[0].set_value(page).run()
        assert not app.exception, page
        assert not app.error, (page,[e.value for e in app.error])

def test_guest_portal_renders():
    app=start(False)
    assert app.title[0].value=='Angie & Brian'
    assert any(x.label=='Save RSVP and meal' for x in app.button)

def test_wrong_invitation_reveals_no_guest_forms():
    app=AppTest.from_file(str(Path(__file__).parents[1]/'app.py'))
    app.session_state.db=Fake(False);app.session_state.user='test-user'
    app.query_params['invite']='some-other-code'
    app.run()
    assert app.warning
    assert not app.text_area
