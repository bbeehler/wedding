-- Wedding planner: access is granted by verified email or explicit planner membership.
create schema if not exists wedding_private;
revoke all on schema wedding_private from public;
grant usage on schema wedding_private to authenticated;
create table public.planners (user_id uuid primary key references auth.users(id) on delete cascade);
alter table public.planners enable row level security;
revoke all on public.planners from anon, authenticated;
grant select on public.planners to authenticated;
create policy self_read on public.planners for select to authenticated using (user_id = (select auth.uid()));
create function wedding_private.is_planner() returns boolean language sql stable security invoker set search_path = '' as $$
 select exists(select 1 from public.planners where user_id = (select auth.uid()));
$$;
revoke all on function wedding_private.is_planner() from public;
grant execute on function wedding_private.is_planner() to authenticated;

create table public.wedding_settings (
 id integer primary key default 1 check(id=1),
 title text not null default 'Angie & Brian',
 welcome_message text not null default 'We cannot wait to celebrate with you at Château Montebello.',
 booking_instructions text not null default 'Room booking instructions will be shared here once confirmed.',
 contact_information text not null default '',
 response_deadline timestamptz not null default '2027-04-30 23:59:00 America/Toronto'
);
insert into public.wedding_settings(id) values (1);
create table public.guests (
 id uuid primary key default gen_random_uuid(), full_name text not null check(length(trim(full_name))>0),
 household text not null default '', portal_email text not null check(portal_email = lower(trim(portal_email)) and position('@' in portal_email)>1),
 invitation_code uuid not null unique default gen_random_uuid(), active boolean not null default true,
 is_child boolean not null default false, table_number text not null default '', created_at timestamptz not null default now()
);
create index guests_portal_email_idx on public.guests(portal_email);
create table public.events (
 id uuid primary key default gen_random_uuid(), title text not null check(length(trim(title))>0),
 event_date date not null check(event_date between '2027-05-28' and '2027-05-30'),
 start_time time, end_time time, location text not null default 'Château Montebello',
 description text not null default '', dress_code text not null default '', published boolean not null default false,
 check(end_time is null or start_time is null or end_time >= start_time)
);
create table public.event_invites (
 id uuid primary key default gen_random_uuid(), guest_id uuid not null references public.guests(id) on delete cascade,
 event_id uuid not null references public.events(id) on delete cascade, unique(guest_id,event_id)
);
create index event_invites_event_idx on public.event_invites(event_id);
create table public.meal_options (
 id uuid primary key default gen_random_uuid(), event_id uuid not null references public.events(id) on delete cascade,
 name text not null check(length(trim(name))>0), description text not null default '', unique(event_id,name), unique(id,event_id)
);
create table public.event_responses (
 id uuid primary key default gen_random_uuid(), guest_id uuid not null, event_id uuid not null,
 rsvp text not null default 'Pending' check(rsvp in ('Pending','Attending','Declined')),
 meal_option_id uuid, unique(guest_id,event_id),
 foreign key(guest_id,event_id) references public.event_invites(guest_id,event_id) on delete cascade,
 foreign key(meal_option_id,event_id) references public.meal_options(id,event_id),
 check(rsvp='Attending' or meal_option_id is null)
);
create index event_responses_meal_idx on public.event_responses(meal_option_id,event_id);
create table public.guest_preferences (
 id uuid primary key default gen_random_uuid(), guest_id uuid not null unique references public.guests(id) on delete cascade,
 dietary_restrictions text not null default '', allergies text not null default '', accessibility_requests text not null default ''
);
create table public.room_bookings (
 id uuid primary key default gen_random_uuid(), guest_id uuid not null unique references public.guests(id) on delete cascade,
 status text not null default 'Not booked' check(status in ('Not booked','Requested','Booked','Cancelled')),
 arrival date not null default '2027-05-28', departure date not null default '2027-05-30',
 room_type text not null default '', confirmation_number text not null default '', notes text not null default '',
 check(departure>arrival)
);
create table public.activity_requests (
 id uuid primary key default gen_random_uuid(), guest_id uuid not null, event_id uuid not null,
 notes text not null default '', rentals_needed boolean not null default false,
 unique(guest_id,event_id), foreign key(guest_id,event_id) references public.event_invites(guest_id,event_id) on delete cascade
);
create table public.appointments (
 id uuid primary key default gen_random_uuid(), guest_id uuid not null references public.guests(id) on delete cascade,
 service text not null check(service in ('Golf','Hair','Makeup')), appointment_date date not null default '2027-05-29',
 start_time time not null, end_time time not null, provider text not null default '', location text not null default '',
 group_name text not null default '', cost numeric(12,2) not null default 0 check(cost>=0),
 paid boolean not null default false, notes text not null default '', check(end_time>start_time),
 unique(guest_id,appointment_date,start_time)
);
create index appointments_guest_idx on public.appointments(guest_id);
create table public.run_of_show (
 id uuid primary key default gen_random_uuid(), event_id uuid references public.events(id) on delete set null,
 day date not null check(day between '2027-05-28' and '2027-05-30'),
 start_time time not null, end_time time not null, activity text not null check(length(trim(activity))>0),
 location text not null default '', owner text not null default '', supplier text not null default '',
 cue text not null default '', notes text not null default '', status text not null default 'Planned'
 check(status in ('Planned','Confirmed','Complete')), check(end_time>=start_time)
);
create index run_of_show_event_idx on public.run_of_show(event_id);
create table public.planning_items (
 id uuid primary key default gen_random_uuid(), category text not null check(category in ('Reception','Decor','Entertainment','Food & beverage','Golf','Hair & makeup','General')),
 title text not null check(length(trim(title))>0), supplier text not null default '', contact text not null default '',
 quantity integer not null default 1 check(quantity>=0), estimated_cost numeric(12,2) not null default 0 check(estimated_cost>=0),
 confirmed_cost numeric(12,2) not null default 0 check(confirmed_cost>=0), paid numeric(12,2) not null default 0 check(paid>=0),
 due_date date, owner text not null default '', status text not null default 'To do' check(status in ('To do','In progress','Confirmed','Complete')),
 notes text not null default ''
);

alter table public.wedding_settings enable row level security;
revoke all on public.wedding_settings from anon, authenticated;
grant select, insert, update, delete on public.wedding_settings to authenticated;
create policy planner_all on public.wedding_settings for all to authenticated using ((select wedding_private.is_planner())) with check ((select wedding_private.is_planner()));

alter table public.guests enable row level security;
revoke all on public.guests from anon, authenticated;
grant select, insert, update, delete on public.guests to authenticated;
create policy planner_all on public.guests for all to authenticated using ((select wedding_private.is_planner())) with check ((select wedding_private.is_planner()));

alter table public.events enable row level security;
revoke all on public.events from anon, authenticated;
grant select, insert, update, delete on public.events to authenticated;
create policy planner_all on public.events for all to authenticated using ((select wedding_private.is_planner())) with check ((select wedding_private.is_planner()));

alter table public.event_invites enable row level security;
revoke all on public.event_invites from anon, authenticated;
grant select, insert, update, delete on public.event_invites to authenticated;
create policy planner_all on public.event_invites for all to authenticated using ((select wedding_private.is_planner())) with check ((select wedding_private.is_planner()));

alter table public.meal_options enable row level security;
revoke all on public.meal_options from anon, authenticated;
grant select, insert, update, delete on public.meal_options to authenticated;
create policy planner_all on public.meal_options for all to authenticated using ((select wedding_private.is_planner())) with check ((select wedding_private.is_planner()));

alter table public.event_responses enable row level security;
revoke all on public.event_responses from anon, authenticated;
grant select, insert, update, delete on public.event_responses to authenticated;
create policy planner_all on public.event_responses for all to authenticated using ((select wedding_private.is_planner())) with check ((select wedding_private.is_planner()));

alter table public.guest_preferences enable row level security;
revoke all on public.guest_preferences from anon, authenticated;
grant select, insert, update, delete on public.guest_preferences to authenticated;
create policy planner_all on public.guest_preferences for all to authenticated using ((select wedding_private.is_planner())) with check ((select wedding_private.is_planner()));

alter table public.room_bookings enable row level security;
revoke all on public.room_bookings from anon, authenticated;
grant select, insert, update, delete on public.room_bookings to authenticated;
create policy planner_all on public.room_bookings for all to authenticated using ((select wedding_private.is_planner())) with check ((select wedding_private.is_planner()));

alter table public.activity_requests enable row level security;
revoke all on public.activity_requests from anon, authenticated;
grant select, insert, update, delete on public.activity_requests to authenticated;
create policy planner_all on public.activity_requests for all to authenticated using ((select wedding_private.is_planner())) with check ((select wedding_private.is_planner()));

alter table public.appointments enable row level security;
revoke all on public.appointments from anon, authenticated;
grant select, insert, update, delete on public.appointments to authenticated;
create policy planner_all on public.appointments for all to authenticated using ((select wedding_private.is_planner())) with check ((select wedding_private.is_planner()));

alter table public.run_of_show enable row level security;
revoke all on public.run_of_show from anon, authenticated;
grant select, insert, update, delete on public.run_of_show to authenticated;
create policy planner_all on public.run_of_show for all to authenticated using ((select wedding_private.is_planner())) with check ((select wedding_private.is_planner()));

alter table public.planning_items enable row level security;
revoke all on public.planning_items from anon, authenticated;
grant select, insert, update, delete on public.planning_items to authenticated;
create policy planner_all on public.planning_items for all to authenticated using ((select wedding_private.is_planner())) with check ((select wedding_private.is_planner()));

create policy own_guest on public.guests for select to authenticated using (
 active and portal_email=lower((select auth.jwt()->>'email')) and (select auth.uid()) is not null
);
create policy guest_settings on public.wedding_settings for select to authenticated using (exists(select 1 from public.guests g where g.active and g.portal_email=lower((select auth.jwt()->>'email')) and (select auth.uid()) is not null));
create policy own_invites on public.event_invites for select to authenticated using (exists(select 1 from public.guests g where g.id=guest_id and g.active and g.portal_email=lower((select auth.jwt()->>'email')) and (select auth.uid()) is not null));
create policy invited_events on public.events for select to authenticated using (published and exists(select 1 from public.event_invites i join public.guests g on g.id=i.guest_id where i.event_id=events.id and g.active and g.portal_email=lower((select auth.jwt()->>'email')) and (select auth.uid()) is not null));
create policy invited_meals on public.meal_options for select to authenticated using (exists(select 1 from public.events e join public.event_invites i on i.event_id=e.id join public.guests g on g.id=i.guest_id where e.id=meal_options.event_id and e.published and g.active and g.portal_email=lower((select auth.jwt()->>'email')) and (select auth.uid()) is not null));
create policy own_appointments on public.appointments for select to authenticated using (exists(select 1 from public.guests g where g.id=guest_id and g.active and g.portal_email=lower((select auth.jwt()->>'email')) and (select auth.uid()) is not null));

create policy own_read on public.event_responses for select to authenticated using (exists(select 1 from public.guests g where g.id=guest_id and g.active and g.portal_email=lower((select auth.jwt()->>'email')) and (select auth.uid()) is not null) and exists(select 1 from public.events e join public.event_invites i on i.event_id=e.id join public.guests g on g.id=i.guest_id where e.id=event_responses.event_id and e.published and g.active and g.portal_email=lower((select auth.jwt()->>'email')) and (select auth.uid()) is not null));
create policy own_insert on public.event_responses for insert to authenticated with check (exists(select 1 from public.guests g where g.id=guest_id and g.active and g.portal_email=lower((select auth.jwt()->>'email')) and (select auth.uid()) is not null) and exists(select 1 from public.events e join public.event_invites i on i.event_id=e.id join public.guests g on g.id=i.guest_id where e.id=event_responses.event_id and e.published and g.active and g.portal_email=lower((select auth.jwt()->>'email')) and (select auth.uid()) is not null) and exists(select 1 from public.wedding_settings s where now()<=s.response_deadline));
create policy own_update on public.event_responses for update to authenticated using (exists(select 1 from public.guests g where g.id=guest_id and g.active and g.portal_email=lower((select auth.jwt()->>'email')) and (select auth.uid()) is not null) and exists(select 1 from public.events e join public.event_invites i on i.event_id=e.id join public.guests g on g.id=i.guest_id where e.id=event_responses.event_id and e.published and g.active and g.portal_email=lower((select auth.jwt()->>'email')) and (select auth.uid()) is not null) and exists(select 1 from public.wedding_settings s where now()<=s.response_deadline)) with check (exists(select 1 from public.guests g where g.id=guest_id and g.active and g.portal_email=lower((select auth.jwt()->>'email')) and (select auth.uid()) is not null) and exists(select 1 from public.events e join public.event_invites i on i.event_id=e.id join public.guests g on g.id=i.guest_id where e.id=event_responses.event_id and e.published and g.active and g.portal_email=lower((select auth.jwt()->>'email')) and (select auth.uid()) is not null) and exists(select 1 from public.wedding_settings s where now()<=s.response_deadline));

create policy own_read on public.guest_preferences for select to authenticated using (exists(select 1 from public.guests g where g.id=guest_id and g.active and g.portal_email=lower((select auth.jwt()->>'email')) and (select auth.uid()) is not null));
create policy own_insert on public.guest_preferences for insert to authenticated with check (exists(select 1 from public.guests g where g.id=guest_id and g.active and g.portal_email=lower((select auth.jwt()->>'email')) and (select auth.uid()) is not null) and exists(select 1 from public.wedding_settings s where now()<=s.response_deadline));
create policy own_update on public.guest_preferences for update to authenticated using (exists(select 1 from public.guests g where g.id=guest_id and g.active and g.portal_email=lower((select auth.jwt()->>'email')) and (select auth.uid()) is not null) and exists(select 1 from public.wedding_settings s where now()<=s.response_deadline)) with check (exists(select 1 from public.guests g where g.id=guest_id and g.active and g.portal_email=lower((select auth.jwt()->>'email')) and (select auth.uid()) is not null) and exists(select 1 from public.wedding_settings s where now()<=s.response_deadline));

create policy own_read on public.room_bookings for select to authenticated using (exists(select 1 from public.guests g where g.id=guest_id and g.active and g.portal_email=lower((select auth.jwt()->>'email')) and (select auth.uid()) is not null));
create policy own_insert on public.room_bookings for insert to authenticated with check (exists(select 1 from public.guests g where g.id=guest_id and g.active and g.portal_email=lower((select auth.jwt()->>'email')) and (select auth.uid()) is not null) and exists(select 1 from public.wedding_settings s where now()<=s.response_deadline));
create policy own_update on public.room_bookings for update to authenticated using (exists(select 1 from public.guests g where g.id=guest_id and g.active and g.portal_email=lower((select auth.jwt()->>'email')) and (select auth.uid()) is not null) and exists(select 1 from public.wedding_settings s where now()<=s.response_deadline)) with check (exists(select 1 from public.guests g where g.id=guest_id and g.active and g.portal_email=lower((select auth.jwt()->>'email')) and (select auth.uid()) is not null) and exists(select 1 from public.wedding_settings s where now()<=s.response_deadline));

create policy own_read on public.activity_requests for select to authenticated using (exists(select 1 from public.guests g where g.id=guest_id and g.active and g.portal_email=lower((select auth.jwt()->>'email')) and (select auth.uid()) is not null) and exists(select 1 from public.events e join public.event_invites i on i.event_id=e.id join public.guests g on g.id=i.guest_id where e.id=activity_requests.event_id and e.published and g.active and g.portal_email=lower((select auth.jwt()->>'email')) and (select auth.uid()) is not null));
create policy own_insert on public.activity_requests for insert to authenticated with check (exists(select 1 from public.guests g where g.id=guest_id and g.active and g.portal_email=lower((select auth.jwt()->>'email')) and (select auth.uid()) is not null) and exists(select 1 from public.events e join public.event_invites i on i.event_id=e.id join public.guests g on g.id=i.guest_id where e.id=activity_requests.event_id and e.published and g.active and g.portal_email=lower((select auth.jwt()->>'email')) and (select auth.uid()) is not null) and exists(select 1 from public.wedding_settings s where now()<=s.response_deadline));
create policy own_update on public.activity_requests for update to authenticated using (exists(select 1 from public.guests g where g.id=guest_id and g.active and g.portal_email=lower((select auth.jwt()->>'email')) and (select auth.uid()) is not null) and exists(select 1 from public.events e join public.event_invites i on i.event_id=e.id join public.guests g on g.id=i.guest_id where e.id=activity_requests.event_id and e.published and g.active and g.portal_email=lower((select auth.jwt()->>'email')) and (select auth.uid()) is not null) and exists(select 1 from public.wedding_settings s where now()<=s.response_deadline)) with check (exists(select 1 from public.guests g where g.id=guest_id and g.active and g.portal_email=lower((select auth.jwt()->>'email')) and (select auth.uid()) is not null) and exists(select 1 from public.events e join public.event_invites i on i.event_id=e.id join public.guests g on g.id=i.guest_id where e.id=activity_requests.event_id and e.published and g.active and g.portal_email=lower((select auth.jwt()->>'email')) and (select auth.uid()) is not null) and exists(select 1 from public.wedding_settings s where now()<=s.response_deadline));

-- Draft placeholders: times, reception date, menus and activities require the couple's confirmation.
insert into public.events(title,event_date,description) values
 ('Welcome gathering','2027-05-28','Draft: details to be confirmed.'),
 ('Wedding reception','2027-05-29','Draft: date and details to be confirmed.'),
 ('Farewell gathering','2027-05-30','Draft: details to be confirmed.'),
 ('Round of golf','2027-05-28','Draft: date, tee times and costs to be confirmed.'),
 ('Hair appointments','2027-05-29','Draft: availability and appointments to be confirmed.'),
 ('Makeup appointments','2027-05-29','Draft: availability and appointments to be confirmed.');
