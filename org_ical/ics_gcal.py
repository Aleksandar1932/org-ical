import argparse
import datetime
import os
import re
import pytz
import logging

import tzlocal
import httplib2
from apiclient import discovery
from bs4 import BeautifulSoup
from icalendar import Calendar, Event, vText
from oauth2client import client, tools
from oauth2client.file import Storage
from apiclient.http import BatchHttpRequest
from pprint import pprint

# If modifying these scopes, delete your previously saved credentials
# at ~/.credentials/calendar-python.json
SCOPES = 'https://www.googleapis.com/auth/calendar'
CLIENT_SECRET_FILE = os.getenv('CLIENT_SECRET_FILE')
APPLICATION_NAME = os.getenv('APPLICATION_NAME')

def argparser():
    parser = argparse.ArgumentParser(
        parents=[tools.argparser],
        description='Outlook .ics file to gcal by gcal API'
    )
    parser.add_argument('--ics', dest='ics', required=True, help='input file')
    parser.add_argument('--cal', dest='cal', default='primary', help='execute to which calendar')
    return parser

def get_credentials(flags):
    """Gets valid user credentials from storage.

    If nothing has been stored, or if the stored credentials are invalid,
    the OAuth2 flow is completed to obtain the new credentials.

    Returns:
        Credentials, the obtained credential.
    """
    home_dir = os.path.expanduser('~')
    credential_dir = os.path.join(home_dir, '.credentials')
    if not os.path.exists(credential_dir):
        os.makedirs(credential_dir)
    credential_path = os.path.join(credential_dir, 'calendar-python.json')

    store = Storage(credential_path)
    credentials = store.get()
    if not credentials or credentials.invalid:
        flow = client.flow_from_clientsecrets(CLIENT_SECRET_FILE, SCOPES)
        flow.user_agent = APPLICATION_NAME
        if flags:
            credentials = tools.run_flow(flow, store, flags)
        else:  # Needed only for compatibility with Python 2.6
            credentials = tools.run(flow, store)
        print('Storing credentials to ' + credential_path)
    return credentials

def get_calendarId(service, summary):
    page_token = None
    while True:
        calendar_list = service.calendarList().list(pageToken=page_token).execute()
        for calendar_list_entry in calendar_list['items']:
            if calendar_list_entry['summary'] == summary:
                return calendar_list_entry['id']
        page_token = calendar_list.get('nextPageToken')
        if not page_token:
            break

def parse_ics(ics):
    events = []
    with open(ics, 'r') as rf:
        ical = Calendar().from_ical(rf.read())
        ical_config = dict(ical.sorted_items())
        for i, comp in enumerate(ical.walk()):
            if comp.name == 'VEVENT':
                event = {}
                for name, prop in comp.property_items():
                    localtz = tzlocal.get_localzone()
                    if name in ['SUMMARY', 'LOCATION']:
                        event[name.lower()] = prop.to_ical().decode('utf-8')

                    elif name == 'DTSTART':
                        if isinstance(prop.dt, datetime.date):
                            prop.dt = datetime.datetime.combine(prop.dt, datetime.datetime.min.time())

                        event['start'] = {
                            'dateTime': prop.dt.isoformat(),
                            'timeZone': str(localtz)
                        }

                    elif name == 'DTEND':
                        if isinstance(prop.dt, datetime.date):
                            prop.dt = datetime.datetime.combine(prop.dt, datetime.datetime.min.time())

                        if (abs(datetime.datetime.fromisoformat(event['start']['dateTime']) - prop.dt).days) == 1:
                            prop.dt = datetime.datetime.combine(prop.dt - datetime.timedelta(days = 1), datetime.datetime.max.time())
                        event['end'] = {
                            'dateTime': prop.dt.isoformat(),
                            'timeZone': str(localtz)
                        }

                    elif name == 'SEQUENCE':
                        event[name.lower()] = prop

                    elif name == 'TRANSP':
                        event['transparency'] = prop.lower()

                    elif name == 'CLASS':
                        event['visibility'] = prop.lower()

                    elif name == 'ORGANIZER':
                        event['organizer'] = {
                            'displayName': prop.params.get('CN') or '',
                            'email': re.match('mailto:(.*)', prop).group(1) or ''
                        }

                    elif name == 'DESCRIPTION':
                        desc = prop.to_ical().decode('utf-8')
                        desc = desc.replace(u'\xa0', u' ')
                        if name.lower() in event:
                            event[name.lower()] = desc + '\r\n' + event[name.lower()]
                        else:
                            event[name.lower()] = desc

                    elif name == 'X-ALT-DESC' and 'description' not in event:
                        soup = BeautifulSoup(prop, 'lxml')
                        desc = soup.body.text.replace(u'\xa0', u' ')
                        if 'description' in event:
                            event['description'] += '\r\n' + desc
                        else:
                            event['description'] = desc

                    elif name == 'ATTENDEE':
                        if 'attendees' not in event:
                            event['attendees'] = []
                        RSVP = prop.params.get('RSVP') or ''
                        RSVP = 'RSVP={}'.format('TRUE:{}'.format(prop) if RSVP == 'TRUE' else RSVP)
                        ROLE = prop.params.get('ROLE') or ''
                        event['attendees'].append({
                            'displayName': prop.params.get('CN') or '',
                            'email': re.match('mailto:(.*)', prop).group(1) or '',
                            'comment': ROLE
                            # 'comment': '{};{}'.format(RSVP, ROLE)
                        })

                    # VALARM: only remind by UI popup
                    elif name == 'ACTION':
                        event['reminders'] = {'useDefault': True}

                    else:
                        # print(name)
                        pass

                events.append(event)

    return events

def cb_insert_event(request_id, response, e):
    summary = response['summary'] if response and 'summary' in response else '?'
    if not e:
        print('({}) - Insert event {}'.format(request_id, summary))
    else:
        print('({}) - Exception {}'.format(request_id, e))

def main(args):
    """The usage of the Google Calendar API.

    Creates a Google Calendar API service object and outputs a list of
    events on the user's calendar.
    """
    logger = logging.getLogger('ics_gcal')
    credentials = get_credentials(args)
    http = credentials.authorize(httplib2.Http())
    service = discovery.build('calendar', 'v3', http=http)
    batch = service.new_batch_http_request(callback=cb_insert_event)

    calendar_id = get_calendarId(service, args.cal)
    if calendar_id is None:
        logger.debug(f"Calendar {args.cal} does not exist! Creating it now")
        return 1

    events = parse_ics(args.ics)

    # create event without attendees
    for i, event in enumerate(events):
        batch.add(service.events().insert(calendarId=calendar_id, body=event))
    batch.execute(http=http)

if __name__ == '__main__':
    parser = argparser()
    main(parser.parse_args())
