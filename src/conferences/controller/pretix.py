# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2023 Digital CUBE <https://digitalcube.rs>

import os
import jwt
import httpx
import logging
import datetime

import shared.ex as ex
import conferences.models as models

log = logging.getLogger('conference_logger')
current_file_dir = os.path.dirname(os.path.abspath(__file__))

rlog = logging.getLogger('redis_logger')


async def fetch_pretix_order(conference, pretix_order_id):
    return await models.PretixOrder.filter(conference=conference, id_pretix_order=pretix_order_id).get_or_none()


def generate_token(pretix_order):
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'secret')

    payload = {
        'pretix_order_id': pretix_order.id_pretix_order,
        'pretix_order_secret': pretix_order.secret,
        'iat': datetime.datetime.utcnow(),
        'exp': datetime.datetime.utcnow() + datetime.timedelta(days=31),
    }
    encoded_jwt = jwt.encode(payload, JWT_SECRET_KEY, algorithm='HS256')

    return encoded_jwt


async def fetch_order_from_prefix(conference, pretix_order_id):
    PRETIX_TOKEN = os.getenv('PRETIX_TOKEN')
    PRETIX_CHECKLIST_ID = os.getenv('PRETIX_CHECKLIST_ID')
    PRETIX_EVENT_ID = os.getenv('PRETIX_EVENT_ID')
    PRETIX_ORGANIZER_ID = os.getenv('PRETIX_ORGANIZER_ID')

    async with httpx.AsyncClient() as client:
        try:
            res = await client.get(
                f'https://pretix.eu/api/v1/organizers/{PRETIX_ORGANIZER_ID}/events/{PRETIX_EVENT_ID}/checkinlists/{PRETIX_CHECKLIST_ID}/positions/?order={pretix_order_id}',
                headers={'Authorization': f'Token {PRETIX_TOKEN}'})

            if res.status_code != 200:
                raise ex.AppException('PRETIX_ERROR', f'Pretix API returned {res.status_code}')

            pretix_data = res.json()

        except Exception as e:
            log.critical(f'Failed to fetch order from pretix: {e}')
            raise

    return pretix_data


async def register_pretix_order(conference, order_code, push_notification_token: str = None, registered_in_open_con_app: bool = None, device=None):
    order_code = order_code.strip().upper()

    pretix_order = await models.PretixOrder.filter(conference=conference, id_pretix_order=order_code).get_or_none()

    if pretix_order:
        if pretix_order.push_notification_token != push_notification_token:
            pretix_order.push_notification_token = push_notification_token
            await pretix_order.save()

        if pretix_order.registered_in_open_con_app != registered_in_open_con_app:
            pretix_order.registered_in_open_con_app = registered_in_open_con_app
            await pretix_order.save()

        if pretix_order.registered_from_device_type != device:
            pretix_order.registered_from_device_type = device
            await pretix_order.save()

        return {'id': str(pretix_order.id), 'token': generate_token(pretix_order), 'created': False}

    pretix_data = await fetch_order_from_prefix(conference, order_code)

    if len(pretix_data['results']) == 0:
        raise ex.AppException(id_message='PRETIX_ORDER_NOT_FOUND', message='Order not found')

    first_name = pretix_data['results'][0]['attendee_name_parts']['given_name']
    last_name = pretix_data['results'][0]['attendee_name_parts']['family_name']
    organization = pretix_data['results'][0]['company']

    email = pretix_data['results'][0]['attendee_email']
    secret = pretix_data['results'][0]['secret']

    secret_per_sub_event = {}
    for p in pretix_data['results']:
        secret_per_sub_event[p['subevent']] = p['secret']

    pretix_order = await models.PretixOrder.create(conference=conference, id_pretix_order=order_code, first_name=first_name,
                                                   last_name=last_name, organization=organization, email=email, secret=secret,
                                                   push_notification_token=push_notification_token,
                                                   secret_per_sub_event=secret_per_sub_event,
                                                   registered_from_device_type=device
                                                   )

    await pretix_order.save()

    logger = logging.getLogger('redis_logger')
    logger.info(f'User registered: {pretix_order.email}')

    return {'id': str(pretix_order.id), 'token': generate_token(pretix_order), 'created': True}


async def pretix_qrcode_scanned(id_conference, secret, id_lane,
                                pretix_order_code,
                                # pretix_attendee_email,
                                # pretix_attendee_first_name,
                                # pretix_attendee_last_name,
                                # pretix_company,
                                ):
    conference = await models.Conference.filter(id=id_conference).get_or_none()
    if not conference:
        raise ex.AppException(id_message='CONFERENCE_NOT_FOUND', message='Conference not found')

    pretix_order = await fetch_pretix_order(conference, pretix_order_code)
    if not pretix_order:
        pretix_order = await register_pretix_order(conference, pretix_order_code, registered_in_open_con_app=False)
        pretix_order = await models.PretixOrder.filter(id=pretix_order['id']).get_or_none()

    try:
        rlog.info(f'User scanned: {pretix_order.first_name} {pretix_order.last_name} <{pretix_order.email}> | registered_in_app: {pretix_order.registered_in_open_con_app}')
    except Exception as e:
        raise
