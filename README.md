# Angie & Brian's Wedding App

A Streamlit wedding planner and private guest portal for **Château Montebello, May 28–30, 2027**.

## Current status

The Supabase database is installed in project `sgentjmoidlpmbjobpco`. The app code is ready to deploy to Streamlit. Hosting, planner accounts and guest email delivery still need the setup below. No invitations have been sent.

The welcome gathering, reception, farewell, golf, hair and makeup events are **unpublished draft placeholders**. Confirm their dates, times, locations and descriptions before publishing. The initial April 30, 2027 response deadline is editable in Settings.

## Launch from GitHub online

1. In Streamlit Community Cloud, create an app using repository `bbeehler/wedding`, branch `feature/wedding-planner`, and entrypoint `app.py`. Select Python **3.12**. If the pull request has been merged, use `main` instead.
2. Open the app's **Settings → Secrets** and add:

   ```toml
   SUPABASE_URL = "https://sgentjmoidlpmbjobpco.supabase.co"
   SUPABASE_PUBLISHABLE_KEY = "YOUR_PUBLISHABLE_KEY"
   APP_BASE_URL = "https://YOUR-APP.streamlit.app"
   ```

   Copy the publishable key from Supabase's API Keys settings. A service-role or secret key is **not needed**. Do not put secrets.toml or guest exports in GitHub.
3. Set up the planner accounts below. You can use planner password sign-in before guest email delivery is configured.
4. Set up email verification below before inviting guests.
5. Add guests, confirm events, assign invitations, add meal options and publish the confirmed events. Save the hotel booking instructions and contact information in Settings.
6. Set the final public app address before downloading invitation QR codes. Changing this address after printing invitations will break the printed links unless you maintain a redirect at the old address.

## First planner accounts

In Supabase **Authentication → Users → Add user**, create an account for each planner using their email and a strong password. Use the dashboard's create-user option, not an email invitation. Confirm the account in the dashboard if necessary.

Then run this in the Supabase SQL Editor, replacing the two placeholders with the exact account emails:

```sql
insert into public.planners(user_id)
select id from auth.users
where lower(email) in ('BRIAN_EMAIL_HERE', 'ANGIE_EMAIL_HERE')
on conflict (user_id) do nothing;
```

Use lowercase email addresses in the placeholders. To grant just one planner, supply just one address. Check that membership was created:

```sql
select u.email from public.planners p
join auth.users u on u.id = p.user_id;
```

Only the database owner can grant planner access. A guest cannot make themselves a planner, and creating an Auth account does not grant access to wedding records. To revoke a planner, delete their membership through the SQL Editor with a specific `user_id` filter.

## Guest email verification

1. Enable the Supabase Email provider and keep email confirmation enabled. Allow new users to sign up for the first OTP sign-in. Guests without a matching invitation email will see no wedding records.
2. Configure **custom SMTP** in Supabase Authentication settings using your email provider's credentials. The default Supabase email service is limited to project-team addresses and is not suitable for wedding guests.
3. In the **Magic Link** email template, include the token:

   ```html
   <h2>Your wedding portal sign-in code</h2>
   <p>Enter this code in the wedding portal: <strong>{{ .Token }}</strong></p>
   <p>If you did not request this code, you can ignore this email.</p>
   ```

   Include `{{ .Token }}` in the **Confirm signup** template too so first-time guests can obtain the code. New free-tier projects require custom SMTP to customize templates.
4. Set the Supabase Site URL to the public Streamlit app address. Review the Auth email rate limits for your invitation volume.
5. Test a QR link and OTP sign-in using a real invited test email before printing invitations. Email delivery has not been tested by this implementation because no sender account has been configured.

References: [Supabase email OTP](https://supabase.com/docs/guides/auth/auth-email-passwordless), [custom SMTP](https://supabase.com/docs/guides/auth/auth-smtp), [Streamlit deployment](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app).

## How guest access works

- Every guest gets a randomly generated QR invitation URL. The URL contains no name or email.
- Scanning opens sign-in. The guest verifies the email saved on their invitation.
- The same `portal_email` on multiple guest records allows one person to manage those records, including children. A household label alone grants no access.
- Guests see their assigned published events, responses, dietary requirements, accommodation and appointments. They cannot read budgets, supplier contacts, internal run-of-show notes, other households or draft events.
- The QR is an invitation shortcut, not a bearer credential. An email address matching an active guest record can also sign in from the home page.
- Replacing a QR invalidates the old link in the app; **deactivating the guest** revokes database access for that guest immediately. Do not use QR replacement as a substitute for revocation.
- Guests can change responses until the configured deadline; planners can make corrections afterward. Deadlines are enforced by the database as well as the UI.
- Signing out clears browser-session data. Reloading the app may require sign-in again.

## Planning workflow

| Page | Purpose |
| --- | --- |
| Overview | Active guest count, outstanding event RSVPs, booked rooms, costs and open tasks |
| Guests | Add and edit individuals, shared sign-in emails, child status and table assignments; deactivate invitations |
| Invitations & QR codes | Assign or remove event invitations; download individual QR PNGs or a ZIP with guest labels |
| Events | Maintain dates, times, locations, dress codes and guest information; explicitly publish confirmed events |
| Rooms | Track a booking under its lead guest, stay dates, room type, confirmation and requests |
| Reception / Decor / Entertainment | Suppliers, quantities, costs, contacts, owners, deadlines and tasks |
| Food & beverage | Event-specific meal options and planning; catering exports are in Reports |
| Golf / Hair & makeup | Requests via event RSVPs, tee times, foursome labels and assigned service appointments |
| Run of show | Separate schedules for all three days, production cues, owners and suppliers; flags overlapping owner assignments |
| Budget & tasks | Estimated and confirmed costs, payments and remaining balances in CAD |
| Reports | RSVP lists, attending-guest meal counts, dietary/allergy lists and activity requests |
| Settings | Welcome copy, booking instructions, contact information and response deadline |

Room records track reservations made directly with the hotel. The app does not reserve rooms, charge cards, book tee times with the venue, or send bulk invitation/reminder emails. Appointments are assigned by planners; guest requests do not automatically reserve a slot. Event calendars and the internal run of show are maintained separately.

## Local development / GitHub Codespaces

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# Fill in the local secrets file, then:
streamlit run app.py
```

The fully pinned `requirements.txt` is the dependency lock for Python 3.12. `requirements.in` lists the main direct dependencies.

## Database and verification

- `supabase/migrations/` contains the initial schema and transactional verification migration, aligned with the remote migration history.
- `docs/schema.sql` is a readable copy of the initial schema. **Do not rerun it on the already configured project.** For a new empty project, apply the migrations in order.
- All public app tables have RLS enabled, explicit privileges, and no anonymous data access. Private helper functions use invoker privileges. No service-role key is used by Streamlit.
- Authenticated Supabase clients live only in the individual Streamlit session and are never globally cached.
- `tests/rls_integration.sql` exercises guest isolation, unpublished/private records, RSVP writes, invalid meal/event combinations, deadline enforcement and deactivation. Synthetic fixtures are rolled back. Run it only from a privileged SQL connection.
- `python -m pytest -q` runs pure-helper and Streamlit page smoke tests without network calls.
- CSV exports protect cells beginning with spreadsheet formula characters. QR archives and guest exports are generated in memory and offered to the planner; they are not stored in the repository.

A live OTP delivery and phone QR scan remain required before guest launch.
