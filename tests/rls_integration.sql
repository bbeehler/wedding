-- Run through a privileged SQL connection. All synthetic fixtures are rolled back.
-- Does not send emails or retain guest records. Failures abort the entire statement.
do $test$
declare
 ga uuid; gb uuid; e1 uuid; e2 uuid; m1 uuid; m2 uuid; uid uuid:=gen_random_uuid(); n integer;
begin
 begin
  insert into public.guests(full_name,portal_email) values ('RLS fixture A','rls-a@example.invalid') returning id into ga;
  insert into public.guests(full_name,portal_email) values ('RLS fixture B','rls-b@example.invalid') returning id into gb;
  insert into public.events(title,event_date,published) values ('RLS event A','2027-05-28',true) returning id into e1;
  insert into public.events(title,event_date,published) values ('RLS event B','2027-05-29',true) returning id into e2;
  insert into public.event_invites(guest_id,event_id) values (ga,e1),(gb,e2);
  insert into public.meal_options(event_id,name) values (e1,'Meal A') returning id into m1;
  insert into public.meal_options(event_id,name) values (e2,'Meal B') returning id into m2;
  insert into public.room_bookings(guest_id) values (gb);
  insert into public.guest_preferences(guest_id,allergies) values (gb,'Private allergy');
  insert into public.run_of_show(day,start_time,end_time,activity,notes) values ('2027-05-28','12:00','13:00','Private cue','Private note');
  insert into public.planning_items(category,title) values ('General','Private budget');
  update public.wedding_settings set response_deadline=now()+interval '1 day' where id=1;
  perform set_config('request.jwt.claims',json_build_object('sub',uid,'email','rls-a@example.invalid','role','authenticated')::text,true);
  set local role authenticated;
  if (select count(*) from public.guests)<>1 then raise exception 'Guest isolation failed'; end if;
  if (select count(*) from public.events)<>1 then raise exception 'Event isolation failed'; end if;
  if (select count(*) from public.meal_options)<>1 then raise exception 'Meal isolation failed'; end if;
  if exists(select 1 from public.room_bookings) or exists(select 1 from public.guest_preferences) then raise exception 'Private guest information exposed'; end if;
  if exists(select 1 from public.run_of_show) or exists(select 1 from public.planning_items) then raise exception 'Planner records exposed'; end if;
  insert into public.event_responses(guest_id,event_id,rsvp,meal_option_id) values (ga,e1,'Attending',m1);
  update public.event_responses set rsvp='Declined',meal_option_id=null where guest_id=ga;
  get diagnostics n=row_count;
  if n<>1 then raise exception 'Own RSVP update failed'; end if;
  insert into public.guest_preferences(guest_id,allergies) values (ga,'Own allergy');
  insert into public.room_bookings(guest_id,status) values (ga,'Requested');
  insert into public.activity_requests(guest_id,event_id,notes) values (ga,e1,'Own request');
  begin
   insert into public.guest_preferences(guest_id,allergies) values (gb,'Intrusion');
   raise exception 'Cross-household insert succeeded';
  exception when insufficient_privilege then null; end;
  update public.room_bookings set notes='Intrusion' where guest_id=gb;
  get diagnostics n=row_count;
  if n<>0 then raise exception 'Cross-household update succeeded'; end if;
  begin
   update public.event_responses set rsvp='Attending',meal_option_id=m2 where guest_id=ga;
   raise exception 'Wrong-event meal accepted';
  exception when foreign_key_violation then null; end;
  begin
   insert into public.event_responses(guest_id,event_id) values (ga,e2);
   raise exception 'Uninvited event accepted';
  exception when insufficient_privilege or foreign_key_violation then null; end;
  reset role;
  update public.wedding_settings set response_deadline=now()-interval '1 day' where id=1;
  set local role authenticated;
  update public.room_bookings set notes='Late update' where guest_id=ga;
  get diagnostics n=row_count;
  if n<>0 then raise exception 'Deadline update accepted'; end if;
  reset role;
  update public.guests set active=false where id=ga;
  set local role authenticated;
  if exists(select 1 from public.guests) or exists(select 1 from public.room_bookings) then raise exception 'Deactivated guest access retained'; end if;
  reset role;
  set local role anon;
  begin
   perform count(*) from public.guests;
   raise exception 'Anonymous guest read accepted';
  exception when insufficient_privilege then null; end;
  reset role;
  -- The nested block rolls back every fixture and setting change.
  raise exception using errcode='P0002',message='All RLS checks passed; rolling back fixtures';
 exception when no_data_found then null;
 end;
end $test$;
