"""Angie & Brian's wedding planner. All data access uses Supabase user JWTs and RLS."""
import io
import os
import uuid
import zipfile
from datetime import date, datetime, time

import pandas as pd
import qrcode
import streamlit as st
from supabase import create_client
from domain import DAYS, TZ, clashes, csv_bytes, invitation_url, responses_open, safe_filename

st.set_page_config(page_title='Angie & Brian | Montebello 2027', page_icon='🤍', layout='wide')
st.markdown('''<style>
.stApp {background:#faf8f3;} h1,h2,h3 {color:#31483f;} h1 {font-family:Georgia,serif;}
[data-testid="stSidebar"] {background:#e9eee7;}
[data-testid="stMetric"] {background:white;border:1px solid #deded3;border-radius:12px;padding:16px;}
</style>''', unsafe_allow_html=True)

def config(name, default=''):
    try:
        return st.secrets.get(name, os.getenv(name, default))
    except st.errors.StreamlitSecretNotFoundError:
        return os.getenv(name, default)

def database():
    # Never cache an authenticated client globally: one client per browser session.
    if 'db' not in st.session_state:
        url = config('SUPABASE_URL', 'https://sgentjmoidlpmbjobpco.supabase.co')
        key = config('SUPABASE_PUBLISHABLE_KEY')
        if not key:
            st.info('The wedding portal is being prepared. Please check back soon.')
            with st.expander('Setup instructions for Angie and Brian'):
                st.write('Add SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY in Streamlit app settings → Secrets. See README.md in GitHub for the full setup.')
            st.stop()
        st.session_state.db = create_client(url, key)
    return st.session_state.db

def rows(table):
    result=[]
    offset=0
    while True:
        batch=db.table(table).select('*').order('user_id' if table=='planners' else 'id').range(offset,offset+499).execute().data
        result.extend(batch)
        if len(batch)<500:
            return result
        offset+=500

def save(table, values, identifier=None, conflict=None):
    if identifier:
        result=db.table(table).update(values).eq('id',identifier).execute()
    elif conflict:
        result=db.table(table).upsert(values,on_conflict=conflict).execute()
    else:
        result=db.table(table).insert(values).execute()
    if not result.data:
        raise ValueError('Nothing was saved. Access or the response deadline may have changed.')
    st.session_state.flash='Your changes have been saved.'
    st.rerun()

def show_table(data, name):
    if not data:
        st.info('No records yet.')
        return
    st.dataframe(pd.DataFrame(data), hide_index=True, width='stretch')
    st.download_button('Download CSV', csv_bytes(data), file_name=f'{safe_filename(name)}.csv', mime='text/csv', key=f'download_{name}')

def label(row):
    return str(row.get('full_name') or row.get('title') or row.get('name') or row.get('activity') or row.get('id',''))

# Field types: text, long, bool, number, money, date, day, time, enum or foreign table.
FIELDS={
 'guests': [('full_name','Full name','text'),('household','Household label','text'),('portal_email','Email used to sign in','text'),('active','Invitation active','bool'),('is_child','Child','bool'),('table_number','Reception table','text')],
 'events': [('title','Event name','text'),('event_date','Date','day'),('start_time','Start time','time'),('end_time','End time','time'),('location','Location','text'),('description','Guest information','long'),('dress_code','Dress code','text'),('published','Publish to invited guests','bool')],
 'meal_options': [('event_id','Event','events'),('name','Meal name','text'),('description','Description / ingredients','long')],
 'room_bookings': [('guest_id','Lead guest for the room','guests'),('status','Booking status',['Not booked','Requested','Booked','Cancelled']),('arrival','Arrival','date'),('departure','Departure','date'),('room_type','Room type','text'),('confirmation_number','Confirmation number','text'),('notes','Booking notes (visible to guest)','long')],
 'appointments': [('guest_id','Guest','guests'),('service','Service',['Golf','Hair','Makeup']),('appointment_date','Date','day'),('start_time','Start time','time'),('end_time','End time','time'),('provider','Provider','text'),('location','Location','text'),('group_name','Foursome / group','text'),('cost','Cost (CAD)','money'),('paid','Paid','bool'),('notes','Notes (visible to guest)','long')],
 'run_of_show': [('day','Day','day'),('start_time','Start','time'),('end_time','End','time'),('activity','Activity / cue name','text'),('location','Location','text'),('owner','Person responsible','text'),('supplier','Supplier','text'),('cue','Production cue','long'),('notes','Internal notes','long'),('status','Status',['Planned','Confirmed','Complete'])],
 'planning_items': [('category','Category',['Reception','Decor','Entertainment','Food & beverage','Golf','Hair & makeup','General']),('title','Item / task','text'),('supplier','Supplier','text'),('contact','Supplier contact','text'),('quantity','Quantity','number'),('estimated_cost','Estimated total (CAD)','money'),('confirmed_cost','Confirmed total (CAD)','money'),('paid','Paid (CAD)','money'),('due_date','Due date','date'),('owner','Assigned to','text'),('status','Status',['To do','In progress','Confirmed','Complete']),('notes','Internal notes','long')]
}

def record_editor(table, filters=None):
    data=rows(table)
    if filters:
        data=[r for r in data if all(r.get(k) in v if isinstance(v,list) else r.get(k)==v for k,v in filters.items())]
    readable=[]
    guest_map={r['id']:r['full_name'] for r in rows('guests')} if table in ('appointments','room_bookings') else {}
    for row in data:
        readable.append({k:guest_map.get(v,v) if k=='guest_id' else v for k,v in row.items() if k not in ('id','invitation_code','created_at')})
    show_table(readable,table)
    choices={'Add new':None}
    choices.update({f'{label(r)} · {r["id"][:8]}':r for r in data})
    selected=st.selectbox('Add or edit a record',list(choices),key=f'edit_{table}')
    existing=choices[selected] or {}
    # Fetch relationship choices before rendering the form.
    relations={kind:rows(kind) for _,_,kind in FIELDS[table] if isinstance(kind,str) and kind in ('guests','events')}
    with st.form(f'form_{table}_{existing.get("id","new")}'):
        values={}
        for field,title,kind in FIELDS[table]:
            default=existing.get(field, (filters or {}).get(field))
            if isinstance(default,list): default=default[0]
            if isinstance(kind,list):
                values[field]=st.selectbox(title,kind,index=kind.index(default) if default in kind else 0)
            elif kind in relations:
                options={r['id']:label(r) for r in relations[kind]}
                values[field]=st.selectbox(title,list(options),index=list(options).index(default) if default in options else 0,format_func=lambda x:options.get(x,''))
            elif kind=='bool':
                values[field]=st.checkbox(title,value=bool(default if default is not None else field=='active'))
            elif kind in ('money','number'):
                values[field]=st.number_input(title,min_value=0.0 if kind=='money' else 0,value=float(default or 0) if kind=='money' else int(default if default is not None else 1),step=1.0 if kind=='money' else 1)
            elif kind in ('date','day'):
                fallback='2027-05-30' if field=='departure' else '2027-05-28'
                if kind=='day':
                    values[field]=st.selectbox(title,DAYS,index=DAYS.index(default) if default in DAYS else 0)
                else:
                    values[field]=st.date_input(title,date.fromisoformat(default or fallback)).isoformat()
            elif kind=='time':
                t=time.fromisoformat(default) if default else time(12,0)
                values[field]=st.time_input(title,t).isoformat()
            elif kind=='long':
                values[field]=st.text_area(title,value=default or '')
            else:
                values[field]=st.text_input(title,value=default or '')
        if st.form_submit_button('Save',type='primary'):
            if 'portal_email' in values:
                values['portal_email']=values['portal_email'].strip().lower()
            if any(values.get(f) in (None,'') for f in ('guest_id','event_id') if f in values):
                st.error('Add the related guest or event first.')
            else:
                save(table,values,existing.get('id'))
    if existing and table!='guests':
        with st.expander('Delete this record'):
            st.caption('Related records may also be removed. This cannot be undone in the app.')
            confirmed=st.checkbox('I want to delete this record',key=f'delete_confirm_{table}_{existing["id"]}')
            if st.button('Delete record',disabled=not confirmed,key=f'delete_{table}'):
                db.table(table).delete().eq('id',existing['id']).execute()
                st.rerun()

def sign_in():
    st.title('Angie & Brian')
    st.subheader('A weekend to remember')
    st.write('Château Montebello · May 28–30, 2027')
    st.write('Welcome! Sign in with the email address associated with your invitation to plan your stay and celebrate with us.')
    with st.form('send_code'):
        email=st.text_input('Email address').strip().lower()
        if st.form_submit_button('Email me a sign-in code',type='primary'):
            if '@' not in email:
                st.error('Please enter your email address.')
            else:
                db.auth.sign_in_with_otp({'email':email,'options':{'should_create_user':True}})
                st.session_state.pending_email=email
                st.success('Check your inbox for your sign-in code.')
    if st.session_state.get('pending_email'):
        with st.form('verify_code'):
            code=st.text_input('Sign-in code',max_chars=12)
            if st.form_submit_button('Open my invitation'):
                auth=db.auth.verify_otp({'email':st.session_state.pending_email,'token':code.strip(),'type':'email'})
                st.session_state.user=auth.user.id
                st.rerun()
    with st.expander('Planner password sign-in'):
        with st.form('password_login'):
            email=st.text_input('Planner email').strip().lower()
            password=st.text_input('Password',type='password')
            if st.form_submit_button('Sign in'):
                auth=db.auth.sign_in_with_password({'email':email,'password':password})
                st.session_state.user=auth.user.id
                st.rerun()

def guest_portal():
    guests=rows('guests')
    if not guests:
        st.info('There is no active invitation linked to this email. Please contact Angie or Brian to confirm the email on your invitation.')
        return
    code=st.query_params.get('invite')
    if code:
        match=next((g for g in guests if g['invitation_code']==code),None)
        if not match:
            st.warning('This invitation link is no longer available or belongs to another email. Please contact Angie or Brian.')
            return
        guests.sort(key=lambda g:g['id']!=match['id'])
    settings=rows('wedding_settings')[0]
    st.title(settings['title'])
    st.caption('CHÂTEAU MONTEBELLO · MAY 28–30, 2027')
    st.write(settings['welcome_message'])
    if settings['contact_information']:
        st.caption(settings['contact_information'])
    is_open=responses_open(settings)
    deadline=datetime.fromisoformat(settings['response_deadline']).astimezone(TZ)
    st.info(f'Responses close {deadline:%B %d, %Y at %I:%M %p} (Montréal time).' if is_open else 'The response deadline has passed. Please contact Angie or Brian for changes.')
    choice=st.selectbox('Manage responses for',guests,format_func=lambda g:g['full_name'])
    gid=choice['id']
    if choice['table_number']:
        st.write(f'Reception table: {choice["table_number"]}')
    tabs=st.tabs(['My events & meals','Dietary & accessibility','My stay','Appointments'])
    events=sorted(rows('events'),key=lambda r:(r['event_date'],r['start_time'] or '23:59'))
    invites={r['event_id'] for r in rows('event_invites') if r['guest_id']==gid}
    meals=rows('meal_options')
    responses={r['event_id']:r for r in rows('event_responses') if r['guest_id']==gid}
    requests={r['event_id']:r for r in rows('activity_requests') if r['guest_id']==gid}
    with tabs[0]:
        if not any(e['id'] in invites for e in events):
            st.info('Your itinerary will appear here once the details are confirmed.')
        for e in events:
            if e['id'] not in invites:
                continue
            with st.container(border=True):
                st.subheader(e['title'])
                st.write(f'{e["event_date"]} · {(e["start_time"] or "Time to be confirmed")[:20]} · {e["location"]}')
                st.write(e['description'])
                if e['dress_code']:
                    st.caption('Dress code: '+e['dress_code'])
                response=responses.get(e['id'],{})
                options={None:'Please select',**{m['id']:m['name']+' '+m['description'] for m in meals if m['event_id']==e['id']}}
                with st.form(f'rsvp_{gid}_{e["id"]}'):
                    statuses=['Pending','Attending','Declined']
                    rsvp=st.radio('Will you join us?',statuses,index=statuses.index(response.get('rsvp','Pending')),horizontal=True)
                    meal=None
                    if len(options)>1:
                        meal=st.selectbox('Your meal',list(options),format_func=lambda x:options[x],index=list(options).index(response.get('meal_option_id')) if response.get('meal_option_id') in options else 0)
                    if st.form_submit_button('Save RSVP and meal',disabled=not is_open):
                        if rsvp=='Attending' and len(options)>1 and meal is None:
                            st.error('Please select your meal.')
                        else:
                            save('event_responses',{'guest_id':gid,'event_id':e['id'],'rsvp':rsvp,'meal_option_id':meal if rsvp=='Attending' else None},conflict='guest_id,event_id')
                with st.expander('Activity or event requests'):
                    req=requests.get(e['id'],{})
                    with st.form(f'activity_{gid}_{e["id"]}'):
                        notes=st.text_area('Requests (for example, golf partners or preferred appointment time)',value=req.get('notes',''))
                        rentals=st.checkbox('Golf club rentals needed (if applicable)',value=req.get('rentals_needed',False))
                        if st.form_submit_button('Save requests',disabled=not is_open):
                            save('activity_requests',{'guest_id':gid,'event_id':e['id'],'notes':notes,'rentals_needed':rentals},conflict='guest_id,event_id')
    with tabs[1]:
        pref=next((r for r in rows('guest_preferences') if r['guest_id']==gid),{})
        st.caption('Angie and Brian will use this information to coordinate with the venue and relevant service providers.')
        with st.form(f'preferences_{gid}'):
            values={'guest_id':gid}
            for f,title in [('dietary_restrictions','Dietary restrictions'),('allergies','Food allergies'),('accessibility_requests','Accessibility requests')]:
                values[f]=st.text_area(title,value=pref.get(f,''))
            if st.form_submit_button('Save my requirements',disabled=not is_open):
                save('guest_preferences',values,conflict='guest_id')
    with tabs[2]:
        st.write(settings['booking_instructions'])
        st.caption('Book directly using the hotel instructions, then record your details here. For a shared room, enter one booking under the lead guest.')
        room=next((r for r in rows('room_bookings') if r['guest_id']==gid),{})
        with st.form(f'room_{gid}'):
            statuses=['Not booked','Requested','Booked','Cancelled']
            status=st.selectbox('Booking status',statuses,index=statuses.index(room.get('status','Not booked')))
            arrival=st.date_input('Check-in',date.fromisoformat(room.get('arrival','2027-05-28')))
            departure=st.date_input('Check-out',date.fromisoformat(room.get('departure','2027-05-30')))
            room_type=st.text_input('Room type',room.get('room_type',''))
            confirmation=st.text_input('Booking confirmation number',room.get('confirmation_number',''))
            notes=st.text_area('Room requests / sharing with',room.get('notes',''))
            if st.form_submit_button('Save accommodation details',disabled=not is_open):
                if departure<=arrival:
                    st.error('Check-out must be after check-in.')
                else:
                    save('room_bookings',{'guest_id':gid,'status':status,'arrival':str(arrival),'departure':str(departure),'room_type':room_type,'confirmation_number':confirmation,'notes':notes},conflict='guest_id')
    with tabs[3]:
        appointments=[{k:v for k,v in a.items() if k not in ('id','guest_id')} for a in rows('appointments') if a['guest_id']==gid]
        st.caption('Assigned golf tee times and hair or makeup appointments will appear here. Use your event RSVP to request participation.')
        show_table(appointments,'my_appointments')

def overview():
    guests=rows('guests'); invites=rows('event_invites'); answers=rows('event_responses'); rooms=rows('room_bookings'); items=rows('planning_items')
    cols=st.columns(4)
    cols[0].metric('Active guests',sum(g['active'] for g in guests))
    cols[1].metric('Event RSVPs outstanding',len(invites)-sum(r['rsvp']!='Pending' for r in answers))
    cols[2].metric('Rooms booked',sum(r['status']=='Booked' for r in rooms))
    cols[3].metric('Confirmed costs',f'${sum(float(i["confirmed_cost"]) for i in items):,.2f}')
    st.subheader('Response counts by event')
    show_table([{'Event':e['title'],'Invited':sum(i['event_id']==e['id'] for i in invites),'Attending':sum(r['event_id']==e['id'] and r['rsvp']=='Attending' for r in answers),'Declined':sum(r['event_id']==e['id'] and r['rsvp']=='Declined' for r in answers)} for e in rows('events')],'event_summary')
    st.subheader('Open tasks')
    show_table([{k:r[k] for k in ('title','category','owner','due_date','status')} for r in items if r['status']!='Complete'],'open_tasks')

def invitations():
    guests=rows('guests'); events=rows('events'); existing=rows('event_invites')
    st.subheader('Assign event invitations')
    st.caption('Only assigned, published events appear in a guest’s portal. Assign each household member separately or select several guests below.')
    with st.form('assign_invites'):
        event=st.selectbox('Event',events,format_func=label)
        selected=st.multiselect('Guests',guests,format_func=lambda g:g['full_name'])
        if st.form_submit_button('Invite selected guests') and event and selected:
            present={(r['guest_id'],r['event_id']) for r in existing}
            additions=[{'guest_id':g['id'],'event_id':event['id']} for g in selected if (g['id'],event['id']) not in present]
            if additions:
                db.table('event_invites').insert(additions).execute()
            st.success('Event invitations saved.')
    with st.expander('Remove an event invitation'):
        gm={g['id']:g['full_name'] for g in guests}; em={e['id']:e['title'] for e in events}
        target=st.selectbox('Invitation',existing,format_func=lambda i:f'{gm.get(i["guest_id"])} / {em.get(i["event_id"])}')
        confirm=st.checkbox('Remove this invitation and its response')
        if st.button('Remove invitation',disabled=not confirm or target is None):
            db.table('event_invites').delete().eq('id',target['id']).execute(); st.rerun()
    st.subheader('Printable guest QR codes')
    st.caption('Each code opens an individual invitation. Email verification protects personal information. Guests sharing a sign-in email can manage one another’s responses.')
    base=st.text_input('Public app address',value=config('APP_BASE_URL'))
    active=[g for g in guests if g['active']]
    selected=st.selectbox('Guest invitation',active,format_func=label)
    if selected and base:
        url=invitation_url(base,selected['invitation_code'])
        png=io.BytesIO(); qrcode.make(url).save(png,format='PNG')
        st.image(png.getvalue(),width=230)
        st.code(url,language=None)
        st.download_button('Download QR PNG',png.getvalue(),file_name=f'{safe_filename(selected["full_name"])}.png',mime='image/png')
        if st.button('Prepare all guest QR codes'):
            archive=io.BytesIO(); manifest=[]
            with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
                for g in active:
                    link=invitation_url(base,g['invitation_code'])
                    name=f'{safe_filename(g["full_name"])}_{g["id"][:8]}.png'
                    output=io.BytesIO(); qrcode.make(link).save(output,format='PNG')
                    z.writestr(name,output.getvalue()); manifest.append({'guest':g['full_name'],'household':g['household'],'filename':name,'invitation_link':link})
                z.writestr('guest_labels.csv',csv_bytes(manifest))
            st.download_button('Download all QR codes and labels',archive.getvalue(),file_name='wedding_invitations.zip',mime='application/zip')
        if st.button('Replace this guest’s QR link'):
            save('guests',{'invitation_code':str(uuid.uuid4())},selected['id'])

def reports():
    gm={g['id']:g['full_name'] for g in rows('guests')}; em={e['id']:e['title'] for e in rows('events')}; mm={m['id']:m['name'] for m in rows('meal_options')}
    prefs={p['guest_id']:p for p in rows('guest_preferences')}
    answers=rows('event_responses')
    st.subheader('Catering list: attending guests')
    catering=[{'Guest':gm.get(r['guest_id']),'Event':em.get(r['event_id']),'Meal':mm.get(r['meal_option_id'],'Not selected'),'Dietary restrictions':prefs.get(r['guest_id'],{}).get('dietary_restrictions',''),'Allergies':prefs.get(r['guest_id'],{}).get('allergies','')} for r in answers if r['rsvp']=='Attending']
    show_table(catering,'catering')
    if catering:
        totals=pd.DataFrame(catering).groupby(['Event','Meal']).size().reset_index(name='Count')
        st.subheader('Meal totals'); st.dataframe(totals,hide_index=True)
    st.subheader('All guest responses')
    show_table([{'Guest':gm.get(r['guest_id']),'Event':em.get(r['event_id']),'RSVP':r['rsvp'],'Meal':mm.get(r['meal_option_id'],'')} for r in answers],'responses')
    st.subheader('Accessibility and dietary requirements')
    show_table([{'Guest':gm.get(g),**{k:v for k,v in p.items() if k not in ('id','guest_id')}} for g,p in prefs.items()],'requirements')
    st.subheader('Activity requests')
    show_table([{'Guest':gm.get(r['guest_id']),'Event':em.get(r['event_id']),'Requests':r['notes'],'Rentals needed':r['rentals_needed']} for r in rows('activity_requests')],'activity_requests')

def settings_editor():
    s=rows('wedding_settings')[0]
    with st.form('settings'):
        title=st.text_input('Welcome title',s['title'])
        welcome=st.text_area('Welcome message',s['welcome_message'])
        booking=st.text_area('Hotel booking instructions',s['booking_instructions'])
        contact=st.text_area('Guest contact information',s['contact_information'])
        deadline=datetime.fromisoformat(s['response_deadline']).astimezone(TZ)
        day=st.date_input('Response deadline (Montréal time)',deadline.date())
        clock=st.time_input('Deadline time',deadline.time())
        if st.form_submit_button('Save settings'):
            save('wedding_settings',{'title':title,'welcome_message':welcome,'booking_instructions':booking,'contact_information':contact,'response_deadline':datetime.combine(day,clock,tzinfo=TZ).isoformat()},1)

def planner():
    st.title('Wedding planning')
    st.caption('ANGIE & BRIAN · MAY 28–30, 2027 · ALL TIMES IN MONTRÉAL TIME')
    pages=['Overview','Guests','Invitations & QR codes','Events','Rooms','Reception','Decor','Entertainment','Food & beverage','Golf','Hair & makeup','Run of show','Budget & tasks','Reports','Settings']
    page=st.sidebar.radio('Planning dashboard',pages)
    if page=='Overview': overview()
    elif page=='Guests':
        st.caption('Use the same portal email for guests managed together, such as a couple or family. Deactivate a guest to revoke portal access.')
        record_editor('guests')
    elif page=='Invitations & QR codes': invitations()
    elif page=='Events':
        st.info('The initial events are unpublished placeholders. Confirm dates and times, assign guests, then publish each event.')
        record_editor('events')
    elif page=='Rooms': record_editor('room_bookings')
    elif page=='Food & beverage':
        a,b=st.tabs(['Menu options','Food & beverage planning'])
        with a: record_editor('meal_options')
        with b: record_editor('planning_items',{'category':page})
    elif page in ('Golf','Hair & makeup'):
        a,b=st.tabs(['Appointments & tee times','Planning'])
        with a:
            for first,second in clashes(rows('appointments'),'appointment_date',resource_field='guest_id'):
                st.warning(f'A guest has overlapping appointments: {first["appointment_date"]}, {first["start_time"]}.')
            record_editor('appointments',{'service':'Golf'} if page=='Golf' else {'service':['Hair','Makeup']})
        with b: record_editor('planning_items',{'category':page})
    elif page=='Run of show':
        all_rows=rows('run_of_show')
        for first,second in clashes(all_rows,'day'):
            st.warning(f'{first["owner"]} has overlapping assignments: {first["activity"]} and {second["activity"]}.')
        for day,tab in zip(DAYS,st.tabs(['Friday, May 28','Saturday, May 29','Sunday, May 30'])):
            with tab:
                schedule=sorted([r for r in all_rows if r['day']==day],key=lambda r:r['start_time'])
                show_table([{k:v for k,v in r.items() if k not in ('id','event_id')} for r in schedule],f'schedule_{day}')
        st.caption('This operational schedule is private. Edit Events to publish the guest itinerary.')
        record_editor('run_of_show')
    elif page=='Budget & tasks':
        items=rows('planning_items'); totals=st.columns(3)
        totals[0].metric('Estimated',f'${sum(float(r["estimated_cost"]) for r in items):,.2f}')
        totals[1].metric('Confirmed',f'${sum(float(r["confirmed_cost"]) for r in items):,.2f}')
        totals[2].metric('Balance',f'${sum(float(r["confirmed_cost"])-float(r["paid"]) for r in items):,.2f}')
        record_editor('planning_items')
    elif page=='Reports': reports()
    elif page=='Settings': settings_editor()
    else: record_editor('planning_items',{'category':page})

try:
    db=database()
    if not st.session_state.get('user'):
        sign_in()
    else:
        # Refresh expired tokens and ask Auth to verify the session on each rerun.
        session=db.auth.get_session()
        if not session:
            st.session_state.clear(); st.rerun()
        db.auth.get_user()
        if st.sidebar.button('Sign out'):
            db.auth.sign_out({'scope':'local'})
            st.session_state.clear(); st.query_params.clear(); st.rerun()
        if st.session_state.get('flash'):
            st.success(st.session_state.pop('flash'))
        is_planner=bool(rows('planners'))
        if is_planner:
            view=st.sidebar.selectbox('Workspace',['Planning dashboard','Guest portal'])
            if view=='Planning dashboard': planner()
            else:
                st.info('Planner preview shows all active guest records. A real guest sees only the records assigned to their email.')
                guest_portal()
        else:
            guest_portal()
except Exception as exc:
    # Do not print payloads, emails, tokens or database detail to the public UI/logs.
    st.error('We could not complete that request. Check your entries and try again. If signing in, request a fresh code or contact Angie or Brian.')
    if isinstance(exc,ValueError):
        st.warning(str(exc))
    st.caption(f'Reference: {type(exc).__name__}')
