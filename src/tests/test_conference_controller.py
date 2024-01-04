# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2023 Digital CUBE <https://digitalcube.rs>

import os
import json
import pytest
import logging
from unittest.mock import patch, AsyncMock, Mock

import conferences.models
from base_test_classes import BaseTest
import datetime

logging.disable(logging.CRITICAL)

os.environ["TEST_MODE"] = "true"

current_file_dir = os.path.dirname(os.path.realpath(__file__))


async def ivo_bookmarks_event1(conference: conferences.models.Conference):
    try:
        with patch('conferences.controller.fetch_order_from_prefix', new_callable=AsyncMock) as fetch_order_from_prefix:
            fetch_order_from_prefix.return_value = {'results': [
                {'order': 'DRXSG', 'attendee_name': 'Igor Jeremic',
                 'attendee_name_parts': {'given_name': 'Ivo', 'family_name': 'Kovacevic'},
                 'company': 'DigitalCUBE',
                 'subevent': '123',
                 'secret': '8stuwespjgtaxwecjgkvtfmycbvupq3r',
                 'attendee_email': 'ivo@digitalcube.rs'}]}
            res = await conferences.controller.register_pretix_order(conference, 'DRXSG', push_notification_token='ExponentPushToken[xxxxxxxxxxxxxxxxxxxxxx]')

    except Exception as e:
        raise

    token = res['token']
    ivo = conferences.controller.decode_token(token)

    import conferences.models as models
    db_ivo = await models.PretixOrder.filter(id_pretix_order=ivo['pretix_order_id']).get_or_none()

    ...

    from conferences.controller import toggle_bookmark_event_session, opencon_serialize
    try:
        cfr = await opencon_serialize(conference)
    except Exception as e:
        raise

    ide_e = None
    for e in cfr['conference']['db']['sessions']:
        s = cfr['conference']['db']['sessions'][e]
        if s['unique_id'] == '2023day1event1':
            ide_e = e
            break

    assert ide_e is not None

    res = await toggle_bookmark_event_session(ivo['pretix_order_id'], event_session_id=ide_e)
    assert res['bookmarked']

    return ide_e, db_ivo


class TestXMLProcessing(BaseTest):

    @pytest.mark.asyncio
    async def test_fetch_xml_content(self):
        from conferences.controller import fetch_xml_content
        content = await fetch_xml_content()
        assert content is not None

        from conferences.controller import add_conference
        res = await add_conference(content, source_uri=os.getenv("XML_URL", None))
        conference = res['conference']
        assert conference is not None

        from conferences.controller import add_conference
        res = await add_conference(content, source_uri=os.getenv("XML_URL", None))
        conference = res['conference']
        assert conference is not None

    @pytest.mark.asyncio
    async def test_read_xml(self):
        from conferences.controller import read_xml_file, opencon_serialize
        content = await read_xml_file(current_file_dir + '/assets/sfscon2023.xml')
        assert content is not None

        from conferences.controller import add_conference
        res = await add_conference(content, source_uri='file://test.xml')
        conference = res['conference']

        from conferences.controller import get_conference
        conference2 = await get_conference(conference.id)

        assert conference.id == conference2.id

        serialized = await opencon_serialize(conference2)

        assert serialized is not None

        print(json.dumps(serialized, indent=1))

    @pytest.mark.asyncio
    async def test_add_conference_2_times_using_same_resource(self):
        from conferences.controller import read_xml_file
        from conferences.controller import add_conference, find_event_by_unique_id, send_changes_to_bookmakers

        content = await read_xml_file(fname=f'{current_file_dir}/assets/sfscon2023_event1day1_0830.xml')
        assert content is not None
        res = await add_conference(content, source_uri='file://test.xml')
        event = await find_event_by_unique_id(res['conference'], '2023day1event1')
        # print('\nbefore', event.id, event.start_date, event.end_date, event.unique_id)

        assert res['created']
        assert not res['changes']

        # await self.ivo_bookmarks_event1()
        # await ivo_bookmarks_event1(_self=self)
        conference = await conferences.controller.get_conference_by_acronym('sfscon2023')
        conference = await conferences.controller.get_conference(conference.id)

        await ivo_bookmarks_event1(conference)

        content = await read_xml_file(fname=f'{current_file_dir}/assets/sfscon2023_event1day1_0835.xml')
        assert content is not None
        res = await add_conference(content, source_uri='file://test.xml')
        # event2 = await find_event_by_unique_id(res['conference'], '2023day1event1')
        # # print('after ', event2.id, event2.start_date, event2.end_date, event2.unique_id)
        #
        # assert not res['created']
        # assert res['changes']
        # assert json.loads(json.dumps(res['changes'], default=lambda x: str(x))) == {
        #     str(event.id): {
        #         "old_start_timestamp": "2023-11-10 08:30:00+01:00",
        #         "new_start_timestamp": "2023-11-11 08:35:00+01:00"
        #     }
        # }
        #
        #
        # res = await send_changes_to_bookmakers(res['conference'], res['changes'], test=True)
        #
        # import pprint
        # pprint.pprint(res)
        ...

    @pytest.mark.asyncio
    async def test_register_users_on_both_days(self):
        from conferences.controller import register_pretix_order, db_add_conference, decode_token, fetch_pretix_order
        conference = await db_add_conference('test conference', 'test', source_uri='test://test')

        res = await register_pretix_order(conference, 'XCGU9', push_notification_token='ExponentPushToken[xxxxxxxxxxxxxxxxxxxxxx]')

        assert res['created']
        assert 'token' in res

        decoded = decode_token(res['token'])
        assert 'pretix_order_id' in decoded
        assert decoded['pretix_order_id'] == 'XCGU9'

    @pytest.mark.asyncio
    async def test_register_via_pretix(self):
        from conferences.controller import register_pretix_order, db_add_conference, decode_token, fetch_pretix_order
        conference = await db_add_conference('test conference', 'test', source_uri='test://test')

        res = await register_pretix_order(conference, 'PHRJM', push_notification_token='ExponentPushToken[xxxxxxxxxxxxxxxxxxxxxx]')

        assert res['created']
        assert 'token' in res

        decoded = decode_token(res['token'])

        assert 'pretix_order_id' in decoded
        assert decoded['pretix_order_id'] == 'PHRJM'

        res = await fetch_pretix_order(conference, 'PHRJM')

        assert res.first_name == 'Igor'
        assert res.last_name == 'Jeremic'
        assert res.email == 'igor@digitalcube.rs'
        assert res.push_notification_token == 'ExponentPushToken[xxxxxxxxxxxxxxxxxxxxxx]'

        res = await register_pretix_order(conference, 'PHRJM')

        assert not res['created']
        assert 'token' in res

        res = await fetch_pretix_order(conference, 'PHRJM')

        assert res.first_name == 'Igor'
        assert res.last_name == 'Jeremic'
        assert res.email == 'igor@digitalcube.rs'
        assert not res.push_notification_token

    @pytest.mark.asyncio
    async def test_download_xml(self):
        from conferences.controller import fetch_xml_content
        content = await fetch_xml_content()
        assert content is not None

        from conferences.controller import add_conference
        res = await add_conference(content, source_uri='file://test.xml')
        conference = res['conference']
        assert conference is not None


class TestRegisteredUser(BaseTest):

    async def async_setup(self):
        await super().async_setup()

        from conferences.controller import read_xml_file
        content = await read_xml_file(current_file_dir + '/assets/sfscon2023.xml')
        assert content is not None

        from conferences.controller import add_conference
        res = await add_conference(content, source_uri='file://test.xml')
        conference = res['conference']

        from conferences.controller import get_conference
        self.conference = await get_conference(conference.id)

    async def test_get_csv(self):
        from conferences.controller import get_conference_by_acronym, get_csv_talks

        conference = await get_conference_by_acronym(self.conference.acronym)

        csv_file = await get_csv_talks(conference.acronym)

        assert csv_file.startswith('/tmp/')
        assert csv_file.endswith('.csv')

    @pytest.mark.asyncio
    async def test_add_stars(self):
        from conferences.controller import get_conference, get_stars

        import conferences.controller as controller

        with patch('conferences.controller.fetch_order_from_prefix', new_callable=AsyncMock) as fetch_order_from_prefix:
            fetch_order_from_prefix.return_value = {'results': [
                {'order': 'PHRJM', 'attendee_name': 'Igor Jeremic',
                 'attendee_name_parts': {'given_name': 'Igor', 'family_name': 'Jeremic'},
                 'company': 'DigitalCUBE',
                 'subevent': '123',
                 'secret': '8stuwespjgtaxwecjgkvtfmycbvupq3r',
                 'attendee_email': 'igor@digitalcube.rs'}]}

            res = await controller.register_pretix_order(self.conference, 'PHRJM', push_notification_token='ExponentPushToken[xxxxxxxxxxxxxxxxxxxxxx]')

        token = res['token']
        igor = controller.decode_token(token)

        assert 'pretix_order_id' in igor
        assert igor['pretix_order_id'] == 'PHRJM'

        with patch('conferences.controller.fetch_order_from_prefix', new_callable=AsyncMock) as fetch_order_from_prefix:
            fetch_order_from_prefix.return_value = {'results': [
                {'order': 'DRXSG', 'attendee_name': 'Igor Jeremic',
                 'attendee_name_parts': {'given_name': 'Ivo', 'family_name': 'Kovacevic'},
                 'company': 'DigitalCUBE',
                 'subevent': '123',
                 'secret': '8stuwespjgtaxwecjgkvtfmycbvupq3r',
                 'attendee_email': 'ivo@digitalcube.rs'}]}
            res = await controller.register_pretix_order(self.conference, 'DRXSG', push_notification_token='ExponentPushToken[xxxxxxxxxxxxxxxxxxxxxx]')

        token = res['token']
        ivo = controller.decode_token(token)

        assert 'pretix_order_id' in ivo
        assert ivo['pretix_order_id'] == 'DRXSG'

        from conferences.controller import add_stars, opencon_serialize

        cfr = await opencon_serialize(self.conference)

        assert cfr['conference_avg_rating'] == {'rates_by_session': {}}  # no votes yet

        event3_session_id = cfr['conference']['idx']['ordered_sessions_by_days']['2023-11-10'][2]

        # igor votes first
        res = await add_stars('PHRJM', event3_session_id, 5)
        assert res == {'avg': 5.0, 'nr': 1, 'my_rate': 5}

        # check ratings in serialized conference
        self.conference = await get_conference(self.conference.id)
        cfr = await opencon_serialize(self.conference)
        assert cfr['conference_avg_rating'] == {'rates_by_session': {str(event3_session_id): [5, 1]}}

        # ivo votes second
        res = await add_stars('DRXSG', event3_session_id, 2)
        assert res == {'avg': round((5.0 + 2.0) / 2, 2), 'nr': 2, 'my_rate': 2}

        # ivor votes again with different vote
        res = await add_stars('DRXSG', event3_session_id, 5)
        assert res == {'avg': round((5.0 + 5.0) / 2, 2), 'nr': 2, 'my_rate': 5}

        # mitar votes

        with patch('conferences.controller.fetch_order_from_prefix', new_callable=AsyncMock) as fetch_order_from_prefix:
            fetch_order_from_prefix.return_value = {'results': [
                {'order': 'DCN73', 'attendee_name': 'Mitar Spasic',
                 'attendee_name_parts': {'given_name': 'Mitar', 'family_name': 'Spasic'},
                 'company': 'DigitalCUBE',
                 'subevent': '123',
                 'secret': '8stuwespjgtaxwecjgkvtfmycbvupq3r',
                 'attendee_email': 'mitar@digitalcube.rs'}]}
            res = await controller.register_pretix_order(self.conference, 'DCN73', push_notification_token='ExponentPushToken[xxxxxxxxxxxxxxxxxxxxxx]')

        token = res['token']

        mitar = controller.decode_token(token)

        assert 'pretix_order_id' in mitar
        assert mitar['pretix_order_id'] == 'DCN73'

        # mitar correct his vote from 5 to 1
        res = await add_stars('DCN73', event3_session_id, 1)
        assert res == {'avg': round((5.0 + 5.0 + 1.0) / 3, 2), 'nr': 3, 'my_rate': 1}

        res = await get_stars('DCN73', event3_session_id)
        assert res == {'avg': round((5.0 + 5.0 + 1.0) / 3, 2), 'nr': 3, 'my_rate': 1}

        res = await add_stars('DCN73', event3_session_id, 2)
        assert res == {'avg': round((5.0 + 5.0 + 2.0) / 3, 2), 'nr': 3, 'my_rate': 2}

        res = await get_stars('DCN73', event3_session_id)
        assert res == {'avg': round((5.0 + 5.0 + 2.0) / 3, 2), 'nr': 3, 'my_rate': 2}

        res = await add_stars('DCN73', event3_session_id, 3)
        assert res == {'avg': round((5.0 + 5.0 + 3.0) / 3, 2), 'nr': 3, 'my_rate': 3}

        res = await get_stars('DCN73', event3_session_id)
        assert res == {'avg': round((5.0 + 5.0 + 3.0) / 3, 2), 'nr': 3, 'my_rate': 3}

        res = await add_stars('DCN73', event3_session_id, 4)
        assert res == {'avg': round((5.0 + 5.0 + 4.0) / 3, 2), 'nr': 3, 'my_rate': 4}

        res = await add_stars('DCN73', event3_session_id, 5)
        assert res == {'avg': round((5.0 + 5.0 + 5.0) / 3, 2), 'nr': 3, 'my_rate': 5}

        # check ratings in serialized conference
        self.conference = await get_conference(self.conference.id)
        cfr = await opencon_serialize(self.conference)
        assert cfr['conference_avg_rating'] == {'rates_by_session': {str(event3_session_id): [5, 3]}}

    @pytest.mark.asyncio
    async def test_bookmark_event_session(self):
        from conferences.controller import register_pretix_order, decode_token, my_bookmarks
        res = await register_pretix_order(self.conference, 'PHRJM', push_notification_token='ExponentPushToken[xxxxxxxxxxxxxxxxxxxxxx]')
        token = res['token']
        decoded = decode_token(token)
        assert 'pretix_order_id' in decoded
        assert decoded['pretix_order_id'] == 'PHRJM'

        from conferences.controller import toggle_bookmark_event_session, opencon_serialize

        cfr = await opencon_serialize(self.conference)
        event_session_id = cfr['conference']['idx']['ordered_sessions_by_days']['2023-11-10'][0]
        event2_session_id = cfr['conference']['idx']['ordered_sessions_by_days']['2023-11-10'][1]
        event3_session_id = cfr['conference']['idx']['ordered_sessions_by_days']['2023-11-10'][2]

        res = await toggle_bookmark_event_session(decoded['pretix_order_id'], event_session_id=event_session_id)
        assert res['bookmarked']

        res = await toggle_bookmark_event_session(decoded['pretix_order_id'], event_session_id=event_session_id)
        assert not res['bookmarked']

        res = await toggle_bookmark_event_session(decoded['pretix_order_id'], event_session_id=event_session_id)
        assert res['bookmarked']
        res = await toggle_bookmark_event_session(decoded['pretix_order_id'], event_session_id=event2_session_id)
        assert res['bookmarked']
        res = await toggle_bookmark_event_session(decoded['pretix_order_id'], event_session_id=event3_session_id)
        assert res['bookmarked']

        assert {event_session_id, event2_session_id, event3_session_id} == await my_bookmarks(decoded['pretix_order_id'])

        res = await toggle_bookmark_event_session(decoded['pretix_order_id'], event_session_id=event2_session_id)
        assert not res['bookmarked']

        assert {event_session_id, event3_session_id} == await my_bookmarks(decoded['pretix_order_id'])

    @pytest.mark.asyncio
    async def test_change_starting_date_for_bookmarked_session(self):

        from conferences.controller import register_pretix_order, decode_token, my_bookmarks, read_xml_file, send_changes_to_bookmakers, find_event_by_unique_id
        await register_pretix_order(self.conference, 'PHRJM', push_notification_token='ExponentPushToken[IGOR]')
        await register_pretix_order(self.conference, 'DRXSG', push_notification_token='ExponentPushToken[IVO]')

        from conferences.controller import toggle_bookmark_event_session, opencon_serialize

        cfr = await opencon_serialize(self.conference)
        event_session_id = cfr['conference']['idx']['ordered_sessions_by_days']['2023-11-10'][0]

        res = await toggle_bookmark_event_session('PHRJM', event_session_id=event_session_id)
        assert res['bookmarked']
        res = await toggle_bookmark_event_session('DRXSG', event_session_id=event_session_id)
        assert res['bookmarked']

        content = await read_xml_file(current_file_dir + '/assets/sfscon2023_event1day1_0835.xml')
        assert content is not None

        from conferences.controller import add_conference
        res = await add_conference(content, source_uri='file://test.xml')

        conference = res['conference']
        assert not res['created']
        assert res['changes']

        event = await find_event_by_unique_id(res['conference'], '2023day1event1')

        assert json.loads(json.dumps(res['changes'], default=lambda x: str(x))) == {
            str(event.id): {
                "old_start_timestamp": "2023-11-10 08:30:00+01:00",
                "new_start_timestamp": "2023-11-11 08:35:00+01:00"
            }
        }

        res = await send_changes_to_bookmakers(res['conference'], res['changes'])

        import pprint
        print('\n')
        pprint.pprint(res)
        #
        # return

        assert res['nr_enqueued'] == 2

    @pytest.mark.asyncio
    async def test_send_notifications_5_minute_before_start_integral(self):

        from conferences.controller import send_notifications_5_minute_before_start

        res = await send_notifications_5_minute_before_start(conference=self.conference,
                                                             now_time=datetime.datetime(2023, 11, 10, 8, 26, 0, ))

        # assert res == {'enqueued_messages': 0, 'test_only': False}

        await ivo_bookmarks_event1(conference=self.conference)

        res = await send_notifications_5_minute_before_start(conference=self.conference,
                                                             now_time=datetime.datetime(2023, 11, 10, 8, 26, 0, ))

        # assert res == {'enqueued_messages': 1, 'test_only': False}

        # again same time / expecting 0

        res = await send_notifications_5_minute_before_start(conference=self.conference,
                                                             now_time=datetime.datetime(2023, 11, 10, 8, 26, 0, ))

        # assert res == {'enqueued_messages': 0, 'test_only': False}

    # async def ivo_bookmarks_event1(self, conference):
    #
    #     with patch('conferences.controller.fetch_order_from_prefix', new_callable=AsyncMock) as fetch_order_from_prefix:
    #         fetch_order_from_prefix.return_value = {'results': [
    #             {'order': 'DRXSG', 'attendee_name': 'Igor Jeremic',
    #              'attendee_name_parts': {'given_name': 'Ivo', 'family_name': 'Kovacevic'},
    #              'company': 'DigitalCUBE',
    #              'subevent': '123',
    #              'secret': '8stuwespjgtaxwecjgkvtfmycbvupq3r',
    #              'attendee_email': 'ivo@digitalcube.rs'}]}
    #         res = await conferences.controller.register_pretix_order(conference, 'DRXSG', push_notification_token='ExponentPushToken[xxxxxxxxxxxxxxxxxxxxxx]')
    #
    #     token = res['token']
    #     ivo = conferences.controller.decode_token(token)
    #
    #     import conferences.models as models
    #     db_ivo = await models.PretixOrder.filter(id_pretix_order=ivo['pretix_order_id']).get_or_none()
    #
    #     ...
    #
    #     from conferences.controller import toggle_bookmark_event_session, opencon_serialize
    #     cfr = await opencon_serialize(conference)
    #
    #     ide_e = None
    #     for e in cfr['conference']['db']['sessions']:
    #         s = cfr['conference']['db']['sessions'][e]
    #         if s['unique_id'] == '2023day1event1':
    #             ide_e = e
    #             break
    #
    #     assert ide_e is not None
    #
    #     res = await toggle_bookmark_event_session(ivo['pretix_order_id'], event_session_id=ide_e)
    #     assert res['bookmarked']
    #
    #     return ide_e, db_ivo

    @pytest.mark.asyncio
    async def test_send_notifications_5_minute_before_start(self):
        import conferences.controller
        import tortoise.timezone

        # let see what we have 9 hours before start
        n = await conferences.controller.extract_all_session_event_which_starts_in_next_5_minutes(self.conference,
                                                                                                  now=tortoise.timezone.make_aware(datetime.datetime(2023, 11, 10, 0, 0, 0, )))
        # assert n == {'ids': {}, 'human_readable': {}}
        print(n)

        # let see what we have 5 minutes before start
        n = await conferences.controller.extract_all_session_event_which_starts_in_next_5_minutes(self.conference,
                                                                                                  now=tortoise.timezone.make_aware(datetime.datetime(2023, 11, 10, 8, 26, 0, )))

        assert n['human_readable'] == {'Check-in': {'start_at': '2023-11-10 08:30:00+01:00', 'start_in': '4:00 minutes', 'to_notify': []}}

        try:
            ide_e, db_ivo = await ivo_bookmarks_event1(conference=self.conference)
        except Exception as e:
            raise

        res = await conferences.controller.extract_all_session_event_which_starts_in_next_5_minutes(self.conference,
                                                                                                    now=tortoise.timezone.make_aware(datetime.datetime(2023, 11, 10, 8, 26, 0, )))

        assert 'human_readable' in res
        assert res['human_readable'] == {'Check-in': {'start_at': '2023-11-10 08:30:00+01:00',
                                                      'start_in': '4:00 minutes',
                                                      'to_notify': ['ivo@digitalcube.rs']}}

        ids = res['ids']

        res = await conferences.controller.enqueue_5minute_before_notifications(self.conference, ids)

        # assert res == {'enqueued_messages': 1, 'test_only': False}

        res = await conferences.controller.enqueue_5minute_before_notifications(self.conference, ids)

        # assert res == {'enqueued_messages': 0, 'test_only': False}


class TestPrinter(TestRegisteredUser):

    async def test(self):
        from conferences.controller import get_conference, get_stars

        import conferences.controller as controller

        lanes = os.getenv('CHECKIN_LANES', None)
        assert lanes is not None

        lanes = json.loads(lanes)
        lane1 = lanes['LANE1']

        res = await controller.pretix_qrcode_scanned(self.conference.id,
                                                     'secret',
                                                     lane1, 'PHRJM')

        # token = res['token']
        # igor = controller.decode_token(token)
        #
        # assert 'pretix_order_id' in igor
        # assert igor['pretix_order_id'] == 'PHRJM'
