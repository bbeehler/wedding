"""Pure helpers shared by the guest portal and planner dashboard."""
import csv
import io
import re
from datetime import datetime
from urllib.parse import urlencode, urlsplit, urlunsplit
from zoneinfo import ZoneInfo

TZ = ZoneInfo('America/Toronto')
DAYS = ['2027-05-28', '2027-05-29', '2027-05-30']

def invitation_url(base, code):
    parts = urlsplit(base.strip())
    if parts.scheme != 'https' or not parts.netloc or parts.username or parts.password:
        raise ValueError('Set the public HTTPS app address before generating invitations.')
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode({'invite': str(code)}), ''))

def csv_bytes(rows):
    if not rows:
        return b''
    fields = list(dict.fromkeys(k for row in rows for k in row))
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    for row in rows:
        writer.writerow({k: ("'" + str(v) if isinstance(v,str) and v.lstrip().startswith(('=','+','-','@')) else v) for k,v in row.items()})
    return output.getvalue().encode('utf-8-sig')

def safe_filename(name):
    return re.sub(r'[^A-Za-z0-9_-]+','_',name).strip('_') or 'guest'

def responses_open(settings, now=None):
    deadline = datetime.fromisoformat(settings['response_deadline'].replace('Z','+00:00'))
    return (now or datetime.now(TZ)) <= deadline

def clashes(rows, day_field, start_field='start_time', end_field='end_time', resource_field='owner'):
    result=[]
    for n, first in enumerate(rows):
        for second in rows[n+1:]:
            resource = str(first.get(resource_field) or '').strip()
            if resource and resource==str(second.get(resource_field) or '').strip() and first.get(day_field)==second.get(day_field):
                if all(x.get(start_field) and x.get(end_field) for x in (first,second)):
                    if first[start_field]<second[end_field] and second[start_field]<first[end_field]:
                        result.append((first,second))
    return result
