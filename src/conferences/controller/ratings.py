# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2023 Digital CUBE <https://digitalcube.rs>

import os
import jwt
import uuid
import json
import redis
import logging

import shared.ex as ex
import conferences.models as models
from .conference import add_flow

log = logging.getLogger('conference_logger')
current_file_dir = os.path.dirname(os.path.abspath(__file__))

rlog = logging.getLogger('redis_logger')


async def update_starred_session(event_session_id: uuid.UUID, my_rate: int):
    try:
        try:
            event_session = await models.EventSession.filter(id=event_session_id).prefetch_related('starred_session').get_or_none()
        except Exception as e:
            log.critical(f'Failed to fetch event session: {e}')
            raise
        if not event_session:
            raise ex.AppException(id_message='EVENT_SESSION_NOT_FOUND', message='Event session not found')

        starred_session = event_session.starred_session
        starred_session.nr_votes = await models.Star.filter(event_session=event_session).count()

        c = 0
        for s in await models.Star.filter(event_session=event_session).all():
            c += s.stars

        starred_session.total_stars = c
        starred_session.avg_stars = event_session.starred_session.total_stars / event_session.starred_session.nr_votes \
            if starred_session.nr_votes else 0

        await starred_session.save()

        # {'avg': round(avg, 2), 'nr': nr, 'my_rate': my}

        return {'avg': round(event_session.starred_session.avg_stars, 2), 'nr': event_session.starred_session.nr_votes, 'my_rate': my_rate}

        # return {'total_stars': event_session.starred_session.total_stars,
        #         'nr_votes': event_session.starred_session.nr_votes,
        #         'avg_stars': event_session.starred_session.avg_stars}

    except Exception as e:
        log.critical(f'Failed to update starred session: {e}')
        raise


async def get_stars(pretix_order_id: str, event_session_id: uuid.UUID):
    pretix_order = await models.PretixOrder.filter(id_pretix_order=pretix_order_id).get_or_none()
    if not pretix_order:
        raise ex.AppException(id_message='PRETIX_ORDER_NOT_FOUND', message='Order not found')

    event_session = await models.EventSession.filter(id=event_session_id).prefetch_related('starred_session').get_or_none()

    if not event_session:
        raise ex.AppException(id_message='EVENT_SESSION_NOT_FOUND', message='Event session not found')

    star = await models.Star.filter(pretix_order=pretix_order, event_session=event_session).get_or_none()

    return {'avg': round(float(event_session.starred_session.avg_stars), 2), 'nr': event_session.starred_session.nr_votes, 'my_rate': star.stars if star else 0}


async def add_stars(pretix_order_id: str, event_session_id: uuid.UUID, stars: int):
    try:

        pretix_order = await models.PretixOrder.filter(id_pretix_order=pretix_order_id).prefetch_related('conference').get_or_none()

        if not pretix_order:
            raise ex.AppException(id_message='PRETIX_ORDER_NOT_FOUND', message='Order not found')

        event_session = await models.EventSession.filter(id=event_session_id).get_or_none()
        if not event_session:
            raise ex.AppException(id_message='EVENT_SESSION_NOT_FOUND', message='Event session not found')

        star = await models.Star.filter(pretix_order=pretix_order, event_session=event_session).get_or_none()
        if not star:
            star = await models.Star.create(pretix_order=pretix_order, event_session=event_session, stars=stars)
        else:
            if star.stars != stars:
                star.stars = stars
                await star.save()
                await event_session.save()

        log.info(f'Added {stars} stars to {event_session_id} by {pretix_order.email}')
        res = await update_starred_session(event_session_id, star.stars)

        rlog.info(f'User {pretix_order.email} Added {stars} stars to {event_session.title} Average is {res["avg"]} for {res["nr"]} votes')

        await add_flow(pretix_order.conference, pretix_order, f'User {pretix_order.email} Added {stars} stars to {event_session.title} Average is {res["avg"]} for {res["nr"]} votes')

        return res

    except Exception as e:
        log.critical(f'Failed to add stars: {e}')
        raise
