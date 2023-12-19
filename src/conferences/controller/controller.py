# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2023 Digital CUBE <https://digitalcube.rs>

import os
import jwt
import json
import logging

import shared.ex as ex
import conferences.models as models

log = logging.getLogger('conference_logger')
current_file_dir = os.path.dirname(os.path.abspath(__file__))

rlog = logging.getLogger('redis_logger')


async def get_conference_attendees(conference_acronym: str, page: int = 1, per_page: int = 7, search: str = ''):
    # if not hasattr('get_conference_attendees', 'fake_attendees'):
    #
    #     with open(current_file_dir+'/../../tests/assets/fake_attendees.json', 'rt') as f:
    #         all_fake_attendees = json.loads(f.read())
    #
    # fake_attendees = []
    # if not search:
    #     fake_attendees = all_fake_attendees
    #
    # else:
    #     for attendee in all_fake_attendees:
    #         if search.lower() in attendee['first_name'].lower() or search.lower() in attendee['last_name'].lower() or search.lower() in attendee['organization'].lower() or search.lower() in \
    #                 attendee['email'].lower() or search.lower() in attendee['pretix_order'].lower():
    #             fake_attendees.append(attendee)
    #

    conference = await models.Conference.filter(acronym=conference_acronym).get_or_none()

    attendees = [a.serialize() for a in await models.PretixOrder.filter(conference=conference, nr_printed_labels__gt=0).order_by('first_name').all()]

    total_pages = len(attendees) / per_page
    if len(attendees) // per_page != len(attendees) / per_page:
        total_pages += 1

    total_pages = int(total_pages)

    prev_page = page - 1 if page > 1 else None
    next_page = page + 1 if page < total_pages else None

    summary = {
        "total_items": len(attendees),
        "total_pages": total_pages,
        "page": page,
        "per_page": per_page,
        "previous_page": prev_page,
        "next_page": next_page,
    }

    offset = (page - 1) * per_page

    return {'header': [
        {'name': 'First Name', 'key': 'first_name', 'width': '100px'},
        {'name': 'Last Name', 'key': 'last_name', 'width': '100px'},
        {'name': 'Organization', 'key': 'organization', 'width': '100px'},
        {'name': 'Email', 'key': 'email', 'width': '100px'},
        {'name': 'Pretix Order', 'key': 'pretix_order', 'width': '100px'},
        {'name': 'Has SFSCON app', 'key': 'has_app', 'width': '100px'},
    ],
        'summary': summary,

        'data': attendees[offset:offset + per_page]}


def decode_token(token):
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'secret')

    decoded_payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=['HS256'])
    return decoded_payload
