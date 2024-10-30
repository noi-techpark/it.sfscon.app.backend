# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2023 Digital CUBE <https://digitalcube.rs>
import csv
import datetime
import io
import json
import logging
import os
import random
import re
import uuid
from typing import Optional

import httpx
import pydantic
import redis
import slugify
import tortoise.timezone
import xmltodict
import yaml
from fastapi import HTTPException, status
from fastapi.responses import StreamingResponse

import conferences.models as models
import shared.ex as ex

log = logging.getLogger('conference_logger')
current_file_dir = os.path.dirname(os.path.abspath(__file__))

rlog = logging.getLogger('redis_logger')
from tortoise.functions import Avg, Count


class ConferenceImportRequestResponse(pydantic.BaseModel):
    id: str
    created: bool
    changes: dict


async def db_add_conference(name, acronym, source_uri):
    try:
        conference = await models.Conference.create(name=name, acronym=acronym, source_uri=source_uri)
        await models.Location.create(name='Noi Tech Park', slug='noi', conference=conference, )

    except Exception as e:
        log.critical(f'Error adding conference {name} {acronym} {source_uri} :: {str(e)}')
        raise

    try:
        entrances = os.getenv("CHECKIN_LANES", None)
        if entrances:
            entrances = json.loads(entrances)

            for entrance in entrances:
                await models.Entrance.create(name=entrance, id=entrances[entrance], conference=conference, )

    except Exception as e:
        log.critical(f'Error parsing ENTRANCES :: {str(e)}')
        raise

    return conference


async def read_xml_file(fname='sfscon2023.xml'):
    with open(fname, 'r') as f:
        content = xmltodict.parse(f.read(), encoding='utf-8')
    return content['schedule']


async def db_add_or_update_tracks(conference, content_tracks):
    order = 0

    tracks_by_name = {}
    cvt = {'#text': 'name', '@color': 'color'}

    for track in content_tracks['track']:
        order += 1
        defaults = {'conference': conference, 'order': order, 'color': 'black'}

        # TODO: Remove this after Luka fix it in XML

        if track == 'Main track - Main track':
            track = 'Main track'

        if type(track) == str:
            defaults['name'] = track
        else:
            for k, v in track.items():
                if k in cvt:
                    defaults[cvt[k]] = v

        defaults['slug'] = slugify.slugify(defaults['name'])

        try:
            db_track = await models.Track.filter(conference=conference, name=defaults['name']).first()
            if not db_track:
                db_track = await models.Track.create(**defaults)
            else:
                await db_track.update_from_dict(defaults)

        except Exception as e:
            log.critical(f'Error adding track {defaults["name"]} :: {str(e)}')
            raise

        tracks_by_name[db_track.name] = db_track

    if 'SFSCON' not in tracks_by_name:
        db_track = await models.Track.filter(conference=conference, name='SFSCON').get_or_none()
        if not db_track:
            db_track = await models.Track.create(
                **{'conference': conference, 'order': -1, 'name': f'SFSCON', 'slug': f'sfscon', 'color': 'black'})

        tracks_by_name['SFSCON'] = db_track

    return tracks_by_name


async def convert_xml_to_dict(xml_text):
    content = xmltodict.parse(xml_text, encoding='utf-8')
    return content['schedule']


def remove_html(text):
    # return text

    if not text:
        return None

    for t in ('<br>', '<br/>', '<br />', '<p>', '</p>'):
        text = text.replace(t, '\n')

    for t in ('<b>', '<B>'):
        if t in text:
            text = text.replace(t, '|Text style={styles.bold}|')

    for t in ('<em>', '<EM>'):
        if t in text:
            text = text.replace(t, '|Text style={styles.italic}|')

    for t in ('</b>', '</B>', '</em>', '</EM>'):
        if t in text:
            text = text.replace(t, '|/Text|')

    # Define a regular expression pattern to match HTML tags
    pattern = re.compile('<.*?>')

    # Use the pattern to remove all HTML tags
    clean_text = re.sub(pattern, '', text)

    clean_text = clean_text.replace('|Text style={styles.bold}|', '<Text style={styles.bold}>')
    clean_text = clean_text.replace('|Text style={styles.italic}|', '<Text style={styles.italic}>')
    clean_text = clean_text.replace('|/Text|', '</Text>')
    # Remove any extra whitespace
    clean_text = ' '.join(clean_text.split())

    return clean_text


async def fetch_xml_content(use_local_xml=False, local_xml_fname='sfscon2024.xml'):
    if use_local_xml:
        current_file_folder = os.path.dirname(os.path.realpath(__file__))
        if use_local_xml:
            with open(current_file_folder + f'/../../tests/assets/{local_xml_fname}', 'r') as f:
                return await convert_xml_to_dict(f.read())

    XML_URL = os.getenv("XML_URL", None)

    if not XML_URL:
        raise ex.AppException('XML_URL_NOT_SET', 'XML_URL not set')

    async with httpx.AsyncClient() as client:
        try:
            res = await client.get(XML_URL)

            if res.status_code != 200:
                raise ex.AppException('ERROR_FETCHING_XML', XML_URL)

            # for debugging purposes
            with open('/tmp/last_saved_xml.xml', 'wt') as f:
                f.write(res.text)

            dict_content = await convert_xml_to_dict(res.text)
            with open('/tmp/last_saved_json.json', 'wt') as f:
                f.write(json.dumps(dict_content, ensure_ascii=False, indent=1))

            return dict_content
        except Exception as e:
            log.critical(f'Error fetching XML from {XML_URL} :: {str(e)}')
            raise


async def add_sessions(conference, content, tracks_by_name):
    db_location = await models.Location.filter(conference=conference, slug='noi').get_or_none()

    changes = {}

    await models.ConferenceLecturer.filter(conference=conference).delete()

    def get_or_raise(key, obj):

        if key == '@unique_id' and not '@unique_id' in obj:
            return None

        return obj[key]

        # # TODO: Ubi ovo kad srede unique  - id obrisi od 143-145 linije
        # if key == '@unique_id':
        #     # if key not in obj:
        #     return obj['@id']
        #
        # if key not in obj:
        #     raise HTTPException(status_code=status.HTTP_406_NOT_ACCEPTABLE,
        #                         detail=f"{key.upper()}_NOT_FOUND")
        # return obj[key]

    # test for duplicated unique_id

    events_by_unique_id = {}

    all_uids = set()
    for day in content['day']:

        for room in day['room']:
            room_event = room['event']
            if type(room_event) == dict:
                room_event = [room_event]
            for event in room_event:
                if type(event) != dict:
                    continue
                unique_id = get_or_raise('@unique_id', event)
                if not unique_id:
                    continue

                if unique_id in all_uids:
                    continue

                all_uids.add(unique_id)

                if unique_id == '2023day1event5':
                    ...
                if unique_id in events_by_unique_id:
                    raise HTTPException(status_code=status.HTTP_406_NOT_ACCEPTABLE,
                                        detail={"code": f"EVENT_UNIQUE_ID_ALREADY_EXISTS",
                                                "message": f"Event {unique_id} already exists"})

                events_by_unique_id[unique_id] = unique_id

    all_uids = set()

    current_sessions_by_unique_id = {
        s.unique_id: s for s in
        await models.EventSession.filter(conference=conference).all()}

    sessions_in_this_xml_by_unique_id = {}

    for day in content['day']:

        date = day.get('@date', None)
        if not date:
            raise HTTPException(status_code=status.HTTP_406_NOT_ACCEPTABLE,
                                detail={"code": "DAY_DATE_NOT_VALID", "message": "Day date is not valid"})

        room_by_name = {}

        for room in day['room']:

            room_name = room.get('@name', None)

            if not room_name:
                raise HTTPException(status_code=status.HTTP_406_NOT_ACCEPTABLE,
                                    detail={"code": "ROOM_NAME_NOT_VALID", "message": "Room name is not valid"})

            room_slug = slugify.slugify(room_name)

            db_room = await models.Room.filter(conference=conference,
                                               location=db_location,
                                               slug=room_slug).first()

            if not db_room:
                db_room = await models.Room.create(conference=conference,
                                                   location=db_location,
                                                   name=room_name, slug=room_slug)

            if db_room.name not in room_by_name:
                room_by_name[db_room.name] = db_room

            room_event = room['event']
            if type(room_event) == dict:
                room_event = [room_event]
            for event in room_event:

                # try:
                #     if event['@id'] == '654a0e4cbd1d807a6ed7109ee6dc4ddb16ef4048a852e':
                #         print("\nFIND FSFE\n")
                # except Exception as e:
                #     ...
                # else:
                #     ...
                # print(event['title'])

                if type(event) != dict:
                    continue
                unique_id = get_or_raise('@unique_id', event)
                if not unique_id:
                    continue

                if unique_id in all_uids:
                    continue

                all_uids.add(unique_id)

                title = get_or_raise('title', event)
                try:
                    url = get_or_raise('url', event)
                except Exception as e:
                    url = None

                slug = slugify.slugify(title)
                track_name = event.get('track', None)
                if type(track_name) == dict:
                    track_name = track_name['#text']

                # TODO: Remove this after Luka fix it in XML

                if track_name in ('SFSCON - Main track', 'Main track - Main track'):
                    track_name = 'SFSCON'  # 'Main track'

                track = tracks_by_name[track_name] if track_name and track_name in tracks_by_name else None
                # event_type = event.get('@type', None)
                event_start = event.get('start', None)
                description = event.get('description', None)
                abstract = event.get('abstract', None)

                # no_bookmark = event.get('@bookmark', False)
                can_bookmark = event.get('@bookmark', "0") == "1"
                can_rate = event.get('@rating', "0") == "1"

                if not can_bookmark:
                    ...
                else:
                    ...

                if event_start and len(event_start) == 5:
                    event_start = datetime.datetime(year=int(date[0:4]),
                                                    month=int(date[5:7]),
                                                    day=int(date[8:10]),
                                                    hour=int(event_start[0:2]),
                                                    minute=int(event_start[3:5]))
                else:
                    event_start = None

                event_duration = event.get('duration', None)
                if event_duration and len(event_duration) == 5:
                    event_duration = int(event_duration[0:2]) * 60 * 60 + int(event_duration[3:5]) * 60
                else:
                    event_duration = None

                try:
                    track_name = track.name
                    room_name = db_room.name

                    if room_name == 'Seminar 2':
                        event_start += datetime.timedelta(milliseconds=1)
                    if room_name == 'Seminar 3':
                        event_start += datetime.timedelta(milliseconds=2)
                    if room_name == 'Seminar 4':
                        event_start += datetime.timedelta(milliseconds=3)
                    if room_name.startswith('Auditorium'):
                        event_start += datetime.timedelta(milliseconds=4)

                    db_event = await models.EventSession.filter(conference=conference, unique_id=unique_id).first()
                    # print("db_event", db_event)
                    if unique_id == '2023day1event5':
                        ...

                    str_start_time = event_start.strftime('%Y-%m-%d %H:%M:%S') if event_start else None

                    if not db_event:
                        db_event = await models.EventSession.create(conference=conference,
                                                                    title=title,
                                                                    url=url,
                                                                    abstract=abstract,
                                                                    description=remove_html(description),
                                                                    unique_id=unique_id,
                                                                    bookmarkable=can_bookmark,
                                                                    rateable=can_rate,
                                                                    track=track,
                                                                    room=db_room,
                                                                    str_start_time=str_start_time,
                                                                    start_date=event_start,
                                                                    duration=event_duration,
                                                                    end_date=event_start + datetime.timedelta(
                                                                        seconds=event_duration) if event_start and event_duration else None,
                                                                    )

                        sessions_in_this_xml_by_unique_id[unique_id] = db_event

                        # await models.StarredSession.create(event_session=db_event,
                        #                                    nr_votes=0,
                        #                                    total_stars=0,
                        #                                    avg_stars=0)
                    else:

                        event_start = tortoise.timezone.make_aware(event_start)
                        if event_start != db_event.start_date:
                            changes[str(db_event.id)] = {'old_start_timestamp': db_event.start_date,
                                                         'new_start_timestamp': event_start}

                        await db_event.update_from_dict({'title': title, 'abstract': abstract,
                                                         'description': description,
                                                         'unique_id': unique_id,
                                                         'bookmarkable': can_bookmark,
                                                         'rateable': can_rate,
                                                         'track': track,
                                                         'duration': event_duration,
                                                         'db_room': db_room,
                                                         'str_start_time': str_start_time,
                                                         'start_date': event_start,
                                                         'end_date': event_start + datetime.timedelta(
                                                             seconds=event_duration) if event_start and event_duration else None})

                        await db_event.save()

                        sessions_in_this_xml_by_unique_id[unique_id] = db_event

                except Exception as e:
                    log.critical(f'Error adding event {title} :: {str(e)}')
                    raise

                persons = event.get('persons', [])

                if persons:
                    persons = persons['person']

                    if type(persons) == dict:
                        persons = [persons]

                    event_persons = []

                    for person in persons:

                        try:
                            db_person = await models.ConferenceLecturer.filter(conference=conference,
                                                                               external_id=person['@id']).get_or_none()
                        except Exception as e:
                            log.critical(f'Error adding person {person["#text"]} :: {str(e)}')
                            raise

                        display_name = person['#text']
                        # bio = person.get('@bio', None)

                        bio = models.ConferenceLecturer.fix_bio(person.get('@bio', None))

                        pid = person.get('@id', None)
                        organization = person.get('@organization', None)
                        thumbnail_url = person.get('@thumbnail', None)
                        first_name = display_name.split(' ')[0].capitalize()
                        last_name = ' '.join(display_name.split(' ')[1:]).capitalize()
                        social_networks = person.get('@socials', None)
                        social_networks = json.loads(social_networks) if social_networks else []

                        if not db_person:
                            try:
                                db_person = await models.ConferenceLecturer.create(conference=conference,
                                                                                   external_id=pid,
                                                                                   bio=remove_html(bio),
                                                                                   social_networks=social_networks,
                                                                                   first_name=first_name,
                                                                                   last_name=last_name,
                                                                                   display_name=display_name,
                                                                                   thumbnail_url=thumbnail_url,
                                                                                   slug=slugify.slugify(display_name),
                                                                                   organization=organization,
                                                                                   )
                            except Exception as e:
                                log.critical(f'Error adding person {person["#text"]} :: {str(e)}')
                                raise
                        else:
                            await db_person.update_from_dict({'bio': remove_html(bio),
                                                              'social_networks': social_networks,
                                                              'first_name': first_name,
                                                              'last_name': last_name,
                                                              'display_name': display_name,
                                                              'thumbnail_url': thumbnail_url,
                                                              'slug': slugify.slugify(display_name),
                                                              'organization': organization,
                                                              })

                            await db_person.save()

                        event_persons.append(db_person)

                    if event_persons:
                        await db_event.fetch_related('lecturers')
                        await db_event.lecturers.add(*event_persons)

    current_uid_keys = set(current_sessions_by_unique_id.keys())
    event_session_uid_keys = set(sessions_in_this_xml_by_unique_id.keys())

    to_delete = None

    if current_uid_keys and current_uid_keys != event_session_uid_keys:
        to_delete = current_uid_keys - event_session_uid_keys
        for ide in to_delete:
            e = current_sessions_by_unique_id[ide]
            changes[str(e.id)] = {'old_start_timestamp': e.start_date, 'new_start_timestamp': None}

        # removing will be later, after sending notifications

    return changes, to_delete


async def send_changes_to_bookmakers(changes, group_4_user=True):
    log.info('-' * 100)
    log.info("send_changes_to_bookmakers")

    changed_sessions = changes.keys()
    # all_anonymous_bookmarks = await models.AnonymousBookmark.filter(session_id__in=changed_sessions).all()

    notification2token = {}

    from html import unescape
    def clean_text(text):
        # Unescape any HTML entities (like &#8211;)
        text = unescape(text)

        # Remove special characters (adjust regex pattern as needed)
        cleaned_text = re.sub(r'[^\w\s.,:;!?-]', '', text)

        return cleaned_text

    from shared.redis_client import RedisClientHandler
    redis_client = RedisClientHandler.get_redis_client()
    # with redis.Redis(host=os.getenv('REDIS_SERVER'), port=6379, db=0) as r:

    if True:

        q = models.EventSession.filter(id__in=changed_sessions)
        for session in await q:
            print("S1", session.id)
            log.info(f"S1 {session.id}")

        q = models.EventSession.filter(id__in=changed_sessions,
                                       anonymous_bookmarks__user__push_notification_token__isnull=False
                                       ).prefetch_related('anonymous_bookmarks',
                                                          'room',
                                                          'anonymous_bookmarks__user'
                                                          ).distinct()

        s = q.sql()

        log.info("X")

        notify_users = {}
        for session in await q:

            log.info('-' * 100)
            log.info(f"Session {session.id}")

            for bookmarks4session in session.anonymous_bookmarks:

                # log.info(f"    bookmarks4session {bookmarks4session}")

                _from = changes[str(session.id)]['old_start_timestamp'].strftime('%m.%d. %H:%M')
                _to = changes[str(session.id)]['new_start_timestamp'].strftime('%m.%d. %H:%M') if \
                    changes[str(session.id)]['new_start_timestamp'] else None

                if changes[str(session.id)]['new_start_timestamp'] and changes[str(session.id)][
                    'old_start_timestamp'].date() == changes[str(session.id)][
                    'new_start_timestamp'].date():
                    _from = changes[str(session.id)]['old_start_timestamp'].strftime('%H:%M')
                    _to = changes[str(session.id)]['new_start_timestamp'].strftime('%H:%M')

                if not _to:
                    notification = "Session '" + clean_text(session.title) + "' has been cancelled"
                else:
                    notification = "Session '" + clean_text(
                        session.title) + "' has been rescheduled from " + _from + " to " + _to + f' in room {session.room.name}'

                if bookmarks4session.user.push_notification_token not in notification2token:
                    notification2token[bookmarks4session.user.push_notification_token] = []
                notification2token[bookmarks4session.user.push_notification_token].append(notification)

                if not group_4_user:
                    pn_payload = {'id': bookmarks4session.user.push_notification_token,
                                  'expo_push_notification_token': bookmarks4session.user.push_notification_token,
                                  'subject': "Event rescheduled",
                                  'message': notification,
                                  'data': {
                                      'command': 'SESSION_START_CHANGED',
                                      'session_id': str(session.id),
                                      'value': changes[str(session.id)]['new_start_timestamp'].strftime(
                                          '%Y-%m-%d %H:%M:%S')
                                  }
                                  }

                    log.info(f"SENDING PUSH NOTIFICATION TO {bookmarks4session.user.push_notification_token}")
                    redis_client.push_message('opencon_push_notification', pn_payload)

                else:
                    if bookmarks4session.user_id not in notify_users:
                        notify_users[bookmarks4session.user_id] = {
                            'token': bookmarks4session.user.push_notification_token, 'sessions': set()}
                    notify_users[bookmarks4session.user_id]['sessions'].add(bookmarks4session.session_id)

        if group_4_user and notify_users:
            for id_user in notify_users:
                pn_payload = {'id': notify_users[id_user]['token'],
                              'expo_push_notification_token': notify_users[id_user]['token'],
                              'subject': "Event rescheduled" if len(
                                  notify_users[id_user]['sessions']) == 1 else "Events rescheduled",
                              'message': "Some of your bookmarked events have been rescheduled",
                              'data': {
                                  'command': 'OPEN_BOOKMARKS',
                              }
                              }
                log.info(f"SENDING PUSH NOTIFICATION TO {notify_users[id_user]['token']}")
                redis_client.push_message('opencon_push_notification', pn_payload)


async def add_conference(content: dict, source_uri: str, force: bool = False, group_notifications_by_user=True):
    conference = await models.Conference.filter(source_uri=source_uri).get_or_none()

    created = False
    if not conference:
        created = True
        conference = await db_add_conference(content['conference']['title'],
                                             content['conference']['acronym'],
                                             source_uri=source_uri
                                             )

    import shared.utils as utils
    checksum = utils.calculate_md5_checksum_for_dict(content)

    if not force and conference.source_document_checksum == checksum:
        return {'conference': conference,
                'created': False,
                'changes': {},
                'checksum_matches': True,
                }
    else:
        conference.source_document_checksum = checksum
        await conference.save()

    content_tracks = content.get('tracks', [])

    tracks_by_name = await db_add_or_update_tracks(conference, content_tracks)
    try:
        changes, to_delete = await add_sessions(conference, content, tracks_by_name)
    except Exception as e:
        raise

    if created:
        changes = {}

    changes_updated = None
    if changes:
        changes_updated = await send_changes_to_bookmakers(changes, group_4_user=group_notifications_by_user)

    if to_delete:
        await models.EventSession.filter(unique_id__in=to_delete).delete()

    return {'conference': conference,
            'created': created,
            'checksum_matches': False,
            'changes': changes,
            'changes_updated': changes_updated
            }


async def get_conference_sessions(conference_acronym):
    conference = await models.Conference.filter(acronym=conference_acronym).get_or_none()
    if not conference:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail={"code": "CONFERENCE_NOT_FOUND", "message": "conference not found"})

    conference = await get_conference(conference.id)
    serialized = await opencon_serialize(conference)

    sessions = []

    bookmark_per_event = {}
    for bpe in await models.Bookmark.filter(pretix_order__conference=conference).prefetch_related('pretix_order').all():
        if str(bpe.event_session_id) not in bookmark_per_event:
            bookmark_per_event[str(bpe.event_session_id)] = 0
        bookmark_per_event[str(bpe.event_session_id)] += 1

    rate_per_event = {}
    for rpe in await models.StarredSession.filter(event_session__conference=conference).prefetch_related(
            'event_session').all():
        rate_per_event[str(rpe.event_session_id)] = rpe.total_stars / rpe.nr_votes if rpe.nr_votes else ' '

    for day in serialized['conference']['idx']['ordered_sessions_by_days']:
        for id_session in serialized['conference']['idx']['ordered_sessions_by_days'][day]:
            session = serialized['conference']['db']['sessions'][id_session]

            sessions.append({
                'event': session['title'],
                'speakers': ', '.join(
                    [serialized['conference']['db']['lecturers'][id_lecturer]['display_name'] for id_lecturer in
                     session['id_lecturers']]),
                'date': session['date'],
                'bookmarks': bookmark_per_event[str(id_session)] if id_session in bookmark_per_event else 0,
                'rating': rate_per_event[str(id_session)] if str(id_session) in rate_per_event else ' '

                # 'bookmarks': random.randint(0, 100),
                # 'rating': round(random.randint(0, 500) / 100, 2)
            })

    return {'header': [
        {'name': 'Event', 'key': 'event', 'width': '100px'},
        {'name': 'Speakers', 'key': 'speakers', 'width': '100px'},
        {'name': 'Date', 'key': 'date', 'width': '100px'},
        {'name': 'Bookmarks', 'key': 'bookmarks', 'width': '100px'},
        {'name': 'Rating', 'key': 'rating', 'width': '100px'},
    ], 'data': sessions}


async def find_event_by_unique_id(conferece, unique_id):
    return await models.EventSession.filter(conference=conferece, unique_id=unique_id).get_or_none()


async def get_all_conferences():
    try:

        logger = logging.getLogger('redis_logger')
        logger.info('This is a test log message')

        x = [conference.serialize() for conference in await models.Conference.all()]
        return x
    except Exception as e:
        log.critical(f'Error getting all conferences :: {str(e)}')
        raise


async def get_pretix_order(conference: models.Conference, id_pretix_order: str):
    try:
        return await models.PretixOrder.filter(conference=conference, id_pretix_order=id_pretix_order).get_or_none()
    except Exception as e:
        log.critical(f'Error getting pretix order {id_pretix_order} :: {str(e)}')
        raise


async def get_dashboard():
    return {
        'total_users': 33,
        'total_bookmarks': 34,
        'total_ratings': 35,
    }


async def csv_users():
    conference = await get_current_conference()
    if not conference:
        raise HTTPException(status_code=404, detail={"code": "CONFERENCE_NOT_FOUND", "message": "Conference not found"})

    all_users = await models.UserAnonymous.all().prefetch_related('bookmarks', 'bookmarks__session', 'rates')

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID', 'Bookmarks', 'Number of ratings', 'Registered'])

    for user in all_users:
        id = user.id
        bookmarks = len(user.bookmarks)
        nr_ratings = len(user.rates)
        register_at = user.created.strftime('%Y-%m-%d %H:%M:%S')

        writer.writerow([id, bookmarks, nr_ratings, register_at])

    output.seek(0)

    filename = f"sfs2024_anonymous_users_on_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={
            'Content-Disposition': f'attachment; filename="{filename}"'
        }
    )


async def get_all_anonymous_users_with_bookmarked_sessions(order_field: Optional[str] = None,
                                                           order_direction: Optional[models.SortOrder] = None):
    conference = await get_current_conference()
    if not conference:
        raise HTTPException(status_code=404, detail={"code": "CONFERENCE_NOT_FOUND", "message": "Conference not found"})

    all_users = await models.UserAnonymous.all().prefetch_related('bookmarks', 'bookmarks__session', 'rates')

    users_data = [
        {
            'id': user.id,
            'bookmarks': len([b.session.title for b in user.bookmarks]),
            'nr_ratings': len(user.rates),
            'register_at': str(user.created)
        }
        for user in all_users
    ]

    # Apply sorting if specified
    if order_field and order_direction:
        reverse = order_direction == models.SortOrder.DESCENDING
        if order_field == 'register_at':
            users_data.sort(key=lambda x: x['register_at'], reverse=reverse)
        elif order_field in ['bookmarks', 'nr_ratings']:
            users_data.sort(key=lambda x: x[order_field], reverse=reverse)

    return users_data


async def csv_sessions():
    conference = await get_current_conference()
    if not conference:
        raise HTTPException(status_code=404, detail={"code": "CONFERENCE_NOT_FOUND", "message": "Conference not found"})

    all_sessions = await models.EventSession.filter(conference=conference).prefetch_related('anonymous_rates',
                                                                                            'lecturers',
                                                                                            'anonymous_bookmarks').all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Title', 'Speakers', 'Bookmarks', 'Rates', 'Avg rate'])

    for session in all_sessions:
        title = session.title
        speakers = ', '.join([lecturer.display_name for lecturer in session.lecturers])
        bookmarks = len(session.anonymous_bookmarks)
        rates = len(session.anonymous_rates)
        avg_rate = sum([r.rate for r in session.anonymous_rates]) / len(
            session.anonymous_rates) if session.anonymous_rates else None

        writer.writerow([title, speakers, bookmarks, rates, avg_rate])

    output.seek(0)

    filename = f"sfs2024_sessions_on_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={
            'Content-Disposition': f'attachment; filename="{filename}"'
        }
    )


async def get_sessions_by_rate(order_field: Optional[str] = None, order_direction: Optional[models.SortOrder] = None):
    conference = await get_current_conference()
    if not conference:
        raise HTTPException(status_code=404, detail={"code": "CONFERENCE_NOT_FOUND", "message": "Conference not found"})

    # Fetch all sessions related to the current conference
    all_sessions = await models.EventSession.filter(
        conference=conference
    ).prefetch_related('anonymous_rates', 'lecturers', 'anonymous_bookmarks').all()

    # Prepare session data
    sessions_data = [
        {
            'title': session.title,
            'bookmarks': len(session.anonymous_bookmarks),
            'speakers': ', '.join([lecturer.display_name for lecturer in session.lecturers]),
            'rates': len(session.anonymous_rates),
            'avg_rate': sum(r.rate for r in session.anonymous_rates) / len(
                session.anonymous_rates) if session.anonymous_rates else None
        }
        for session in all_sessions
    ]

    # Apply sorting if specified
    if order_field and order_direction:
        reverse = order_direction == models.SortOrder.DESCENDING

        # Sorting for different fields
        if order_field == 'avg_rate':
            rated_sessions = [s for s in sessions_data if s['avg_rate'] is not None]
            unrated_sessions = [s for s in sessions_data if s['avg_rate'] is None]

            rated_sessions.sort(key=lambda x: -x['avg_rate'], reverse=reverse)

            sessions_data = rated_sessions + unrated_sessions
        elif order_field == 'bookmarks':
            sessions_data.sort(
                key=lambda x: (x['bookmarks'] is None, -x['bookmarks'] if x['bookmarks'] is not None else 0),
                reverse=reverse)
        elif order_field == 'rates':
            sessions_data.sort(key=lambda x: (x['rates'] is None, -x['rates'] if x['rates'] is not None else 0),
                               reverse=reverse)

    return sessions_data


async def get_event_summary():
    conference = await get_current_conference()
    if not conference:
        raise HTTPException(status_code=404, detail={"code": "CONFERENCE_NOT_FOUND", "message": "Conference not found"})

    all_users = await models.UserAnonymous.all()
    all_sessions = await models.EventSession.filter(conference=conference).all()
    all_bookmarks = await models.AnonymousBookmark.filter(session__conference=conference).all()
    all_rates = await models.AnonymousRate.filter(session__conference=conference).all()

    return {
        'all_users': len(all_users),
        'total_sessions': len(all_sessions),
        'total_bookmarks': len(all_bookmarks),
        'total_rates': len(all_rates)
    }


async def get_current_conference():
    conference = await models.Conference.filter().prefetch_related('tracks',
                                                                   'locations',
                                                                   'event_sessions',
                                                                   'event_sessions__track',
                                                                   'event_sessions__room',
                                                                   # 'event_sessions__room__location',
                                                                   'event_sessions__lecturers',
                                                                   'rooms',
                                                                   # 'rooms__location',
                                                                   'lecturers',
                                                                   'lecturers__event_sessions',
                                                                   # 'event_sessions__starred_session',

                                                                   'event_sessions__anonymous_bookmarks',
                                                                   'event_sessions__anonymous_rates',

                                                                   ).order_by('-created').first()

    if not conference:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail={"code": "CONFERENCE_NOT_FOUND", "message": "conference not found"})
    return conference


#
# async def get_conference(id_conference: uuid.UUID):
#     conference = await models.Conference.filter(id=id_conference).prefetch_related('tracks',
#                                                                                    'locations',
#                                                                                    'event_sessions',
#                                                                                    'event_sessions__track',
#                                                                                    'event_sessions__room',
#                                                                                    # 'event_sessions__room__location',
#                                                                                    'event_sessions__lecturers',
#                                                                                    'rooms',
#                                                                                    # 'rooms__location',
#                                                                                    'lecturers',
#                                                                                    'lecturers__event_sessions',
#                                                                                    # 'event_sessions__starred_session',
#
#                                                                                    'event_sessions__anonymous_bookmarks',
#                                                                                    'event_sessions__anonymous_rates',
#
#                                                                                    ).get_or_none()
#
#     return conference


async def authorize_user(push_notification_token: str = None):
    # log.info(f"AUTHORIZING NEW ANONYMOUS USER push_notification_token={push_notification_token}")
    anonymous = models.UserAnonymous()  # push_notification_token=push_notification_token)
    await anonymous.save()
    return str(anonymous.id)


async def get_user(id_user: uuid.UUID):
    return await models.UserAnonymous.filter(id=id_user).get_or_none()


async def bookmark_session(id_user, id_session):
    user = await models.UserAnonymous.filter(id=id_user).get_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail={"code": "USER_NOT_FOUND", "message": "user not found"})

    session = await models.EventSession.filter(id=id_session).get_or_none()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail={"code": "SESSION_NOT_FOUND", "message": "session not found"})

    try:
        current_bookmark = await models.AnonymousBookmark.filter(user=user, session=session).get_or_none()
    except Exception as e:
        raise

    if not current_bookmark:
        await models.AnonymousBookmark.create(user=user, session=session)
        return {'bookmarked': True}
    else:
        await current_bookmark.delete()
    return {'bookmarked': False}


def now():
    return datetime.datetime.now()


async def rate_session(id_user, id_session, rate):
    if rate < 1 or rate > 5:
        raise HTTPException(status_code=status.HTTP_406_NOT_ACCEPTABLE,
                            detail={"code": "RATE_NOT_VALID", "message": "rate not valid, use number between 1 and 5"})

    user = await models.UserAnonymous.filter(id=id_user).get_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail={"code": "USER_NOT_FOUND", "message": "user not found"})

    session = await models.EventSession.filter(id=id_session).get_or_none()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail={"code": "SESSION_NOT_FOUND", "message": "session not found"})

    if not session.rateable:
        raise HTTPException(status_code=status.HTTP_406_NOT_ACCEPTABLE,
                            detail={"code": "SESSION_IS_NOT_RATEABLE", "message": "session is not rateable"})

    session_start_datetime_str = f'{session.start_date}'

    s_now = str(now())
    if str(now())[:19] <= session_start_datetime_str[:19]:
        raise HTTPException(status_code=status.HTTP_406_NOT_ACCEPTABLE,
                            detail={"code": "CAN_NOT_RATE_SESSION_IN_FUTURE",
                                    "message": "Rating is only possible after the talk has started."})

    try:
        current_rate = await models.AnonymousRate.filter(user=user, session=session).get_or_none()
    except Exception as e:
        raise

    if not current_rate:
        await models.AnonymousRate.create(user=user, session=session, rate=rate)
    else:
        if current_rate.rate != rate:
            await current_rate.update_from_dict({'rate': rate})
            await current_rate.save()

    all_rates = await models.AnonymousRate.filter(session=session).all()
    avg_rate = sum([rate.rate for rate in all_rates]) / len(all_rates) if all_rates else 0

    return {'avg_rate': avg_rate,
            'total_rates': len(all_rates),
            }


async def do_import_xml(request):
    content = await fetch_xml_content(request.use_local_xml, request.local_xml_fname)
    XML_URL = os.getenv("XML_URL", None)

    try:
        res = await add_conference(content, XML_URL, force=True,
                                   group_notifications_by_user=request.group_notifications_by_user)
    except Exception as e:
        raise
    conference = res['conference']

    return ConferenceImportRequestResponse(id=str(conference.id), created=res['created'], changes=res['changes'])


async def opencon_serialize_static(conference):
    return await opencon_serialize_anonymous(None, conference)


async def opencon_serialize_anonymous(user_id, conference, last_updated=None):
    next_try_in_ms = 3000000
    db_last_updated = str(tortoise.timezone.make_naive(conference.last_updated))

    conference_avg_rating = {'rates_by_session': {},
                             'my_rate_by_session': {}
                             }
    for session in conference.event_sessions:
        if session.anonymous_rates:
            all_rates_for_session = [r.rate for r in session.anonymous_rates]
            if all_rates_for_session:
                conference_avg_rating['rates_by_session'][str(session.id)] = [
                    sum(all_rates_for_session) / len(all_rates_for_session),
                    len(all_rates_for_session)]  # [session.anonymous_rates.avg_stars,
            # session.anonymous_rates.nr_votes]

    if user_id:
        user = await models.UserAnonymous.filter(id=user_id).prefetch_related('bookmarks', 'rates').get_or_none()
        bookmarks = [bookmark.session_id for bookmark in user.bookmarks]
        conference_avg_rating['my_rate_by_session'] = {str(rate.session_id): rate.rate for rate in user.rates}
    else:
        bookmarks = []

    if last_updated and last_updated >= db_last_updated:
        return {'last_updated': db_last_updated,
                'ratings': conference_avg_rating,
                'bookmarks': bookmarks,
                'next_try_in_ms': next_try_in_ms,
                'conference': None
                }

    db = {}
    idx = {}

    with open(current_file_dir + '/../../tests/assets/sfs2024streaming.yaml', 'r') as f:
        streaming_links = yaml.load(f, yaml.Loader)

    idx['ordered_sponsors'] = []

    db['tracks'] = {str(track.id): track.serialize() for track in conference.tracks}
    db['locations'] = {str(location.id): location.serialize() for location in conference.locations}
    db['rooms'] = {str(room.id): room.serialize() for room in conference.rooms}
    db['sessions'] = {str(session.id): session.serialize(streaming_links) for session in conference.event_sessions}
    db['lecturers'] = {str(lecturer.id): lecturer.serialize() for lecturer in conference.lecturers}
    db['sponsors'] = {}

    days = set()
    for s in db['sessions'].values():
        days.add(s['date'])

    idx['ordered_lecturers_by_display_name'] = [l['id'] for l in
                                                sorted(db['lecturers'].values(), key=lambda x: x['display_name'])]
    idx['ordered_sessions_by_days'] = {d: [s['id'] for s in db['sessions'].values() if s['date'] == d] for d in
                                       sorted(list(days))}
    idx['ordered_sessions_by_tracks'] = {t: [s['id'] for s in db['sessions'].values() if s['id_track'] == t] for t in
                                         db['tracks'].keys()}
    idx['days'] = sorted(list(days))

    with open(current_file_dir + '/../../tests/assets/sfscon2024sponsors.yaml', 'r') as f:
        db['sponsors'] = yaml.load(f, yaml.Loader)

    re_ordered_lecturers = {}
    for l in idx['ordered_lecturers_by_display_name']:
        re_ordered_lecturers[l] = db['lecturers'][l]

    db['lecturers'] = re_ordered_lecturers

    return {'last_updated': db_last_updated,
            'ratings': conference_avg_rating,
            'next_try_in_ms': next_try_in_ms,
            'bookmarks': bookmarks,
            'conference': {'acronym': str(conference.acronym),
                           'db': db,
                           'idx': idx
                           }
            }
