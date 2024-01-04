# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2023 Digital CUBE <https://digitalcube.rs>

import os
import json
import uuid
import redis
import logging

import shared.ex as ex
import conferences.models as models

log = logging.getLogger('conference_logger')
current_file_dir = os.path.dirname(os.path.abspath(__file__))

rlog = logging.getLogger('redis_logger')


async def toggle_bookmark_event_session(pretix_order_id: str, event_session_id: uuid.UUID):
    try:
        pretix_order = await models.PretixOrder.filter(id_pretix_order=pretix_order_id).prefetch_related('conference').get_or_none()
        if not pretix_order:
            raise ex.AppException(id_message='PRETIX_ORDER_NOT_FOUND', message='Order not found')

        from .conference import get_conference, get_pretix_order, add_flow
        conference = pretix_order.conference

        event_session = await models.EventSession.filter(id=event_session_id).get_or_none()
        if not event_session:
            raise ex.AppException(id_message='EVENT_SESSION_NOT_FOUND', message='Event session not found')

        bookmark = await models.Bookmark.filter(pretix_order=pretix_order, event_session=event_session).get_or_none()
        if not bookmark:
            await models.Bookmark.create(pretix_order=pretix_order, event_session=event_session)
            rlog.info(f'User {pretix_order.email} bookmarked event {event_session.title}')

            await add_flow(conference, pretix_order, f'User {pretix_order.email} bookmarked event {event_session.title}')

            return {'bookmarked': True}

        await bookmark.delete()
        rlog.info(f'User {pretix_order.email} removed bookmark from event {event_session.title}')

        await add_flow(conference, pretix_order, f'User {pretix_order.email} removed bookmark from event {event_session.title}')

        return {'bookmarked': False}

    except Exception as e:
        log.critical(f'Failed to toggle bookmark for {pretix_order_id} and {event_session_id} :: {e}')
        raise


async def my_bookmarks(pretix_order_id: str):
    try:
        pretix_order = await models.PretixOrder.filter(id_pretix_order=pretix_order_id).get_or_none()
        if not pretix_order:
            raise ex.AppException(id_message='PRETIX_ORDER_NOT_FOUND', message='Order not found')

        return set([str(b.event_session_id) for b in await models.Bookmark.filter(pretix_order=pretix_order).all()])

    except Exception as e:
        raise


async def send_changes_to_bookmakers(conference, changes, test: bool = True):
    changed_sessions = changes.keys()

    event_sessions = await models.EventSession.filter(conference=conference, id__in=changed_sessions).prefetch_related('bookmarks',
                                                                                                                       'room',
                                                                                                                       'bookmarks__pretix_order').all()

    if not event_sessions:
        return {'nr_enqueued': 0, 'test': test, 'logs': []}

    nr_enqueued = 0

    with redis.Redis(host=os.getenv('REDIS_SERVER'), port=6379, db=0) as r:

        for event_session in event_sessions:
            event_change = changes[str(event_session.id)]
            for bookmark in event_session.bookmarks:
                if bookmark.pretix_order.push_notification_token:

                    _start_dt = event_change['new_start_timestamp'] if 'new_start_timestamp' in event_change else event_session.start_date
                    _start_date = _start_dt.strftime('%d %b')
                    _start_time = _start_dt.strftime('%H:%M')

                    text = f'The event "{event_session.title}" time has been changed to {_start_time} {_start_date} in room {event_session.room.name}'

                    push_notification_token = models.PushNotificationQueue(
                        pretix_order=bookmark.pretix_order,
                        subject='Event time has been changed',
                        message=text,
                    )
                    await push_notification_token.save()
                    nr_enqueued += 1

                    try:
                        # !!! Synchronous call - ignore pycharm warning about coroutine, redis is not aioredis
                        r.rpush('opencon_push_notification', json.dumps({'id': str(push_notification_token.id),
                                                                        'expo_push_notification_token': bookmark.pretix_order.push_notification_token,
                                                                        'subject': push_notification_token.subject,
                                                                        'message': push_notification_token.message
                                                                        }))
                    except Exception as e:
                        log.critical(f'Failed to enqueue push notification for {push_notification_token.pretix_order.id_pretix_order}')
                        raise

                    # for message in p.listen():
                    #     print(message)

    return {'nr_enqueued': nr_enqueued}
