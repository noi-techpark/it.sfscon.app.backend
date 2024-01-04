# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2023 Digital CUBE <https://digitalcube.rs>

import os
import uuid
import json
import logging
import pydantic

from typing import Optional
from fastapi import Request
from fastapi.exceptions import HTTPException

from app import get_app
import conferences.models as models
import conferences.controller as controller

app = get_app()


class ScanPretixQRCodeRequest(pydantic.BaseModel):
    pretix_response: dict
    pretix_checkin_response: Optional[dict] = None


'''
/api/conferences/5a25539b-b8f2-4b9d-ad7e-d607bb248835/scans/lanes/5a25539b-b8f2-4b9d-ad7e-d607bb248835/d8cpm24fyuv2nn73zasrzgbcynfcfxd3
'''


@app.post('/api/conferences/{id_conference}z`l/scans/lanes/{id_lane}/{secret}', )
async def scan_pretix_qr_code(id_conference: uuid.UUID, id_lane: uuid.UUID, secret: str, request: ScanPretixQRCodeRequest):
    if not request.pretix_response:
        raise HTTPException(status_code=406, detail='PRETIX_RESPONSE_MISSING')

    if request.pretix_response['count'] < 1:
        raise HTTPException(status_code=406, detail='PRETIX_RESPONSE_COUNT_MISSING')

    if not request.pretix_response['results'][0]['order']:
        raise HTTPException(status_code=406, detail='PRETIX_RESPONSE_ORDER_MISSING')

    order_code = request.pretix_response['results'][0]['order']

    # try:
    #     attendee_email = request.pretix_response['results'][0]['attendee_email']
    #     attendee_first_name = request.pretix_response['results'][0]['attendee_name_parts']['given_name']
    #     attendee_last_name = request.pretix_response['results'][0]['attendee_name_parts']['family_name']
    #     company = request.pretix_response['results'][0]['company']
    # except Exception as e:
    #     logging.critical(f'Failed to parse pretix response: {e}')
    #     raise HTTPException(status_code=406, detail='PRETIX_RESPONSE_DATA_MISSING')

    conference = await controller.get_conference(id_conference=id_conference)

    lane = await models.Entrance.filter(id=id_lane).get_or_none()

    res = await controller.pretix_qrcode_scanned(conference.id,
                                                 secret,
                                                 id_lane,
                                                 order_code,
                                                 # attendee_email,
                                                 # attendee_first_name,
                                                 # attendee_last_name,
                                                 # company,
                                                 )

    pretix_order = await models.PretixOrder.filter(id_pretix_order=order_code).get_or_none()

    pretix_order.nr_printed_labels += 1
    await pretix_order.save()

    text = f"Scanned QR code for order {order_code} on lane {lane.name}, {pretix_order}"

    await controller.add_flow(conference=conference, pretix_order=pretix_order, text=text,
                              data={'pretix_response': request.pretix_response,
                                    'pretix_checkin_response': request.pretix_checkin_response})

    if request.pretix_checkin_response:
        if 'status' in request.pretix_checkin_response and request.pretix_checkin_response['status'] == 'error':
            reason = request.pretix_checkin_response['reason'] if 'reason' in request.pretix_checkin_response else 'UNKNOWN REASON'
            text = f'Checkin failed for order {order_code} on lane {lane.name}, reason: {reason}'
        else:
            text = f"Checked in order {order_code} on lane {lane.name}"

        await controller.add_flow(conference=conference, pretix_order=pretix_order, text=text,
                                  data={'pretix_response': request.pretix_response,
                                        'pretix_checkin_response': request.pretix_checkin_response})

    return res


@app.post('/api/printers/unregister/{id_lane}')
async def unregister(id_lane, request: Request):
    lane = await models.Entrance.filter(id=id_lane).get_or_none()
    if not lane:
        raise HTTPException(status_code=404, detail='LANE_NOT_FOUND')

    rlog = logging.getLogger('redis_logger')

    x_forwarded_for = request.headers.get("x-forwarded-for")
    if x_forwarded_for:
        client_ip = x_forwarded_for.split(",")[0]
    else:
        client_ip = request.client.host

    rlog.info(f"Printer on lane {lane.name} successfully unregistered from {client_ip}")


@app.post('/api/printers/register/{id_lane}')
async def register_printer_and_retrieve_credentials(id_lane, request: Request):
    lane = await models.Entrance.filter(id=id_lane).get_or_none()

    if not lane:
        raise HTTPException(status_code=404, detail='LANE_NOT_FOUND')

    rlog = logging.getLogger('redis_logger')

    x_forwarded_for = request.headers.get("x-forwarded-for")
    if x_forwarded_for:
        client_ip = x_forwarded_for.split(",")[0]
    else:
        client_ip = request.client.host

    conference = await models.Conference.filter(id=lane.conference_id).get_or_none()

    rlog.info(f"Printer on lane {lane.name} successfully registered from {client_ip}")

    LANE2PORT = os.getenv('LANE2PORT', default='{}')
    LANE2PORT = json.loads(LANE2PORT)
    if lane.name in LANE2PORT:
        port = LANE2PORT[lane.name]
    else:
        raise HTTPException(status_code=404, detail='LANE_PORT_FOUND')

    return {
        'id': str(lane.id),
        'id_conference': str(conference.id),
        "name": str(lane.name),
        'external_port': port,
        'pretix': {'token': os.getenv('PRETIX_TOKEN'),
                   'checklist_id': os.getenv('PRETIX_CHECKLIST_ID'),
                   'event_id': os.getenv('PRETIX_EVENT_ID'),
                   'organizer_id': os.getenv('PRETIX_ORGANIZER_ID'),
                   },
        'telegram': {
            'bot_token': os.getenv('TELEGRAM_BOT_TOKEN'),
            'chat_id': os.getenv('TELEGRAM_CHAT_ID'),
        }}


@app.post('/api/printers/timeout/{id_lane}')
async def timeout_printing(id_lane: uuid.UUID, request: Request):
    lane = await models.Entrance.filter(id=id_lane).get_or_none()
    if not lane:
        raise HTTPException(status_code=404, detail='LANE_NOT_FOUND')

    rlog = logging.getLogger('redis_logger')

    rlog.info(f"TIMEOUT while print on lane {lane.name}")

    return {
        'id': str(lane.id),
    }


@app.post('/api/printers/printed/{id_lane}/{secret}')
async def successfully_printed(id_lane: uuid.UUID, secret: str, request: Request):
    lane = await models.Entrance.filter(id=id_lane).get_or_none()
    if not lane:
        raise HTTPException(status_code=404, detail='LANE_NOT_FOUND')

    rlog = logging.getLogger('redis_logger')

    rlog.info(f"SUCCESSFULLY PRINTED {secret} on LANE {lane.name}")

    return {
        'id': str(lane.id),
    }
