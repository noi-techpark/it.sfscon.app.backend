# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2023 Digital CUBE <https://digitalcube.rs>

import os
import json
import redis
import logging
import datetime

import tortoise.timezone

import shared.ex as ex
from .conference import add_flow
import conferences.models as models

log = logging.getLogger('conference_logger')
current_file_dir = os.path.dirname(os.path.abspath(__file__))

rlog = logging.getLogger('redis_logger')


def sec2minutes(seconds):
    mm = seconds // 60
    ss = seconds % 60
    return f'{mm}:{ss:02}'


async def extract_all_session_event_which_starts_in_next_5_minutes(conference, now=None):
    if not now:
        now = tortoise.timezone.now()
        now = now + datetime.timedelta(hours=1)
    else:
        if tortoise.timezone.is_naive(now):
            now = tortoise.timezone.make_aware(now)

    q = models.EventSession.filter(conference=conference,
                                   start_date__gte=now,
                                   start_date__lte=now + datetime.timedelta(minutes=5))
    print(q.sql())

    sessions = await models.EventSession.filter(conference=conference,
                                                start_date__gte=now,
                                                start_date__lte=now + datetime.timedelta(minutes=5)).all()

    to_notify_by_session_emails = {}
    to_notify_by_session = {}
    if sessions:
        for session in sessions:
            bookmarkers_to_notify = await models.Bookmark.filter(event_session=session,
                                                                 pretix_order__push_notification_token__isnull=False).prefetch_related('pretix_order').all()

            to_notify_by_session[str(session.id)] = [str(bookmark.pretix_order.id) for bookmark in bookmarkers_to_notify]
            to_notify_by_session_emails[session.title] = {'start_at': str(session.start_date),
                                                          'start_in': sec2minutes((session.start_date - now).seconds) + ' minutes',
                                                          'to_notify': [bookmark.pretix_order.email for bookmark in bookmarkers_to_notify]}

    return {'ids': to_notify_by_session,
            'human_readable': to_notify_by_session_emails,
            'now': str(now)
            }


async def send_notifications_5_minute_before_start(conference: models.Conference, now_time: datetime.datetime = None, test_only: bool = False):
    # let see what we have 9 hours before start
    res = await extract_all_session_event_which_starts_in_next_5_minutes(conference, now=now_time)
    now_time = res['now']
    return await enqueue_5minute_before_notifications(conference, res['ids'], test_only=test_only, now=now_time)


async def enqueue_notification(pretix_order: models.PretixOrder, subject: str, message: str):
    # pretix_order = await models.PretixOrder.filter(id_pretix_order=id_pretix_order).get_or_none()
    # if not pretix_order:
    #     raise ex.AppException('PRETIX_ORDER_NOT_FOUND', id_pretix_order)

    if not pretix_order.push_notification_token:
        raise ex.AppException('PUSH_NOTIFICATION_TOKEN_NOT_SET', pretix_order.id)

    with redis.Redis(host=os.getenv('REDIS_SERVER'), port=6379, db=0) as r:
        push_notification_token = models.PushNotificationQueue(
            pretix_order=pretix_order,
            subject=subject,
            message=message,
        )
        await push_notification_token.save()

        # !!! Synchronous call - ignore pycharm warning about coroutine, redis is not aioredis
        r.rpush('opencon_push_notification', json.dumps({'id': str(push_notification_token.id),
                                                        'expo_push_notification_token': pretix_order.push_notification_token,
                                                        'subject': subject,
                                                        'message': message
                                                        }))


async def enqueue_5minute_before_notifications(conference, event_id_2_user_ids, test_only=False, now=None):
    log.info(f"enqueue_5minute_before_notifications: {conference.acronym}")

    eids = list(event_id_2_user_ids.keys())
    if not eids:
        log.info('No events to enqueue notifications for 5 minute before start')
        return {'enqueued_messages': 0, 'test_only': test_only, 'now': str(now)}

    events = [e for e in await models.EventSession.filter(id__in=eids, notification5min_sent__isnull=True).prefetch_related('room').all()]

    if not events:
        log.info('No events that are not already notified to enqueue notifications for 5 minute before start')
        return {'enqueued_messages': 0,  'test_only': test_only, 'now': str(now)}

    log.info(f'Found {len(events)} events to enqueue notifications for 5 minute before start')

    users2notify = set()
    for event in events:
        for user_id in event_id_2_user_ids[str(event.id)]:
            users2notify.add(user_id)

    log.info(f'Found {len(users2notify)} users to enqueue notifications for 5 minute before start')

    users2notify = {str(u.id): u for u in await models.PretixOrder.filter(id__in=users2notify).all()}

    if not users2notify:
        log.info(f'nno users to be notieied for 5 minute before start')
        return {'enqueued_messages': 0,  'test_only': test_only, 'now': str(now)}

    notified = 0
    _log = []
    rlog_1_msg = []
    for event in events:
        user_ids = event_id_2_user_ids[str(event.id)]
        for user_id in user_ids:
            user = users2notify[str(user_id)]
            if user.push_notification_token:
                text = f'{event.title} begins at {event.start_date.time().strftime("%H:%M")} at {event.room.name}'
                _log.append(str(users2notify[user_id])+': '+text)
                log.info(f'sending notification {text} to {user.email}')
                rlog_1_msg.append(f'sending notification: {text} to {user.email}')


                if not test_only:
                    await add_flow(conference, user, text)
                    await enqueue_notification(user, 'The event will start shortly', text)

                notified += 1

        if not test_only:
            event.notification5min_sent = True
            await event.save()

    rlog.info('\n'.join(rlog_1_msg))

    if test_only:
        return {'enqueued_messages': notified,
                'log': _log,
                'test_only': test_only,
                'now': str(now)
                }

    log.info(f'notified {notified} users')
    return {'enqueued_messages': notified,  'test_only': test_only, 'now': str(now)}
