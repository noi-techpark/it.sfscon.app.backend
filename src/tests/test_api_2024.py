# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2023 Digital CUBE <https://digitalcube.rs>

import datetime
import json
import logging
import os
import unittest
import unittest.mock

import dotenv
from base_test_classes import BaseAPITest
from httpx import AsyncClient

os.environ["TEST_MODE"] = "true"

dotenv.load_dotenv()

logging.disable(logging.CRITICAL)

from unittest.mock import patch

import fakeredis

from shared.redis_client import RedisClientHandler


def get_local_xml_content():
    try:
        with open(f'{os.path.dirname(os.path.realpath(__file__))}/assets/sfscon2024.xml', 'r') as f:
            return f.read()
    except Exception as e:
        raise


class TestAPIBasic(BaseAPITest):

    async def setup(self):
        self.import_modules(['src.conferences.api'])

    async def test_get_conference_as_non_authorized_user_expect_401(self):
        async with AsyncClient(app=self.app, base_url="http://test") as ac:
            response = await ac.get("/api/conference")
        assert response.status_code == 401

    async def test_authorize_user_and_get_conference_expect_404(self):
        async with AsyncClient(app=self.app, base_url="http://test") as ac:
            response = await ac.post("/api/authorize")
            assert response.status_code == 200
            token = response.json()['token']

            response = await ac.get("/api/conference", headers={"Authorization": f"Bearer {token}"})
            assert response.status_code == 404

    async def test_import_xml(self):
        async with AsyncClient(app=self.app, base_url="http://test") as ac:
            response = await ac.post("/api/import-xml")  # , json={'use_local_xml': False})
            assert response.status_code == 200

    async def test_import_xml_mockuped_result(self):
        async with AsyncClient(app=self.app, base_url="http://test") as ac:
            response = await ac.post("/api/import-xml", json={'use_local_xml': True})
            assert response.status_code == 200

    async def test_add_conference_authorize_user_and_get_conference_expect_200(self):
        async with AsyncClient(app=self.app, base_url="http://test") as ac:
            response = await ac.post("/api/import-xml", json={'use_local_xml': True})
            assert response.status_code == 200

            response = await ac.post("/api/authorize")
            assert response.status_code == 200
            token = response.json()['token']

            response = await ac.get("/api/conference", headers={"Authorization": f"Bearer {token}"})
            assert response.status_code == 200


class Test2024(BaseAPITest):

    async def setup(self):
        self.import_modules(['src.conferences.api'])

        async with AsyncClient(app=self.app, base_url="http://test") as ac:
            response = await ac.post("/api/import-xml", json={'use_local_xml': True})
            assert response.status_code == 200

            response = await ac.post("/api/authorize")
            assert response.status_code == 200
            self.token = response.json()['token']

            response = await ac.post("/api/authorize")
            assert response.status_code == 200
            self.token2 = response.json()['token']

            response = await ac.post("/api/authorize")
            assert response.status_code == 200
            self.token3 = response.json()['token']

        async with AsyncClient(app=self.app, base_url="http://test") as ac:
            response = await ac.get("/api/conference", headers={"Authorization": f"Bearer {self.token}"})
            assert response.status_code == 200
            self.last_updated = response.json()['last_updated']

            self.sessions = response.json()['conference']['db']['sessions']

    async def test_get_conference(self):
        async with AsyncClient(app=self.app, base_url="http://test") as ac:
            response = await ac.get("/api/conference", headers={"Authorization": f"Bearer {self.token}"})
            assert response.status_code == 200

        r = response.json()
        assert 'conference' in r
        assert 'acronym' in r['conference']
        assert r['conference']['acronym'] == 'sfscon-2024'

    async def test_get_conference_with_last_updated_time(self):

        async with AsyncClient(app=self.app, base_url="http://test") as ac:
            response = await ac.get("/api/conference", headers={"Authorization": f"Bearer {self.token}"})
            assert response.status_code == 200

        r = response.json()
        assert 'conference' in r and r['conference']

        last_updated = r['last_updated']

        async with AsyncClient(app=self.app, base_url="http://test") as ac:
            response = await ac.get(f"/api/conference?last_updated={last_updated}",
                                    headers={"Authorization": f"Bearer {self.token}"})
            assert response.status_code == 200

        r = response.json()

        assert 'conference' in r and not r['conference']

    async def test_bookmarks(self):
        async with AsyncClient(app=self.app, base_url="http://test") as ac:
            response = await ac.get(f"/api/conference?last_updated={self.last_updated}",
                                    headers={"Authorization": f"Bearer {self.token}"})
            assert response.status_code == 200

            res = response.json()

            assert 'bookmarks' in res
            assert res['bookmarks'] == []

            id_1st_session = list(self.sessions.keys())[0]
            response = await ac.post(f"/api/sessions/{id_1st_session}/bookmarks/toggle",
                                     headers={"Authorization": f"Bearer {self.token}"})
            assert response.status_code == 200
            assert response.json() == {'bookmarked': True}

            response = await ac.get(f"/api/conference?last_updated={self.last_updated}",
                                    headers={"Authorization": f"Bearer {self.token}"})
            assert response.status_code == 200

            res = response.json()

            assert 'bookmarks' in res
            assert res['bookmarks'] == [id_1st_session]

            response = await ac.post(f"/api/sessions/{id_1st_session}/bookmarks/toggle",
                                     headers={"Authorization": f"Bearer {self.token}"})
            assert response.status_code == 200

            assert response.json() == {'bookmarked': False}
            response = await ac.get(f"/api/conference?last_updated={self.last_updated}",
                                    headers={"Authorization": f"Bearer {self.token}"})
            assert response.status_code == 200

            res = response.json()

            assert 'bookmarks' in res
            assert res['bookmarks'] == []

    async def test_rating(self):
        # ...
        async with AsyncClient(app=self.app, base_url="http://test") as ac:
            response = await ac.get(f"/api/conference?last_updated={self.last_updated}",
                                    headers={"Authorization": f"Bearer {self.token}"})
            assert response.status_code == 200

            res = response.json()

            assert 'ratings' in res
            assert res['ratings'] == {'my_rate_by_session': {}, 'rates_by_session': {}}

            id_1st_session = list(self.sessions.keys())[0]

            with unittest.mock.patch('conferences.controller.conference.now') as mocked_datetime:
                mocked_datetime.return_value = datetime.datetime(2024, 11, 1, 11, 0)

                response = await ac.post(f"/api/sessions/{id_1st_session}/rate", json={'rating': 5},
                                         headers={"Authorization": f"Bearer {self.token}"})

            assert response.status_code == 406
            assert 'detail' in response.json() and 'code' in response.json()['detail']
            assert response.json()['detail']['code'] == 'SESSION_IS_NOT_RATEABLE'

            id_1st_session = None
            for s in self.sessions:
                session = self.sessions[s]
                if session['title'] == 'Let’s all get over the CRA!':
                    id_1st_session = s
                    break

            assert id_1st_session

            with unittest.mock.patch('conferences.controller.conference.now') as mocked_datetime:
                mocked_datetime.return_value = datetime.datetime(2024, 11, 1, 11, 0)
                response = await ac.post(f"/api/sessions/{id_1st_session}/rate", json={'rating': 5}, headers={"Authorization": f"Bearer {self.token}"})

            assert response.status_code == 406
            assert 'detail' in response.json() and 'code' in response.json()['detail']
            assert response.json()['detail']['code'] == 'CAN_NOT_RATE_SESSION_IN_FUTURE'

            with unittest.mock.patch('conferences.controller.conference.now') as mocked_datetime:
                mocked_datetime.return_value = datetime.datetime(2024, 11, 8, 11, 0)
                response = await ac.post(f"/api/sessions/{id_1st_session}/rate", json={'rating': 5},
                                         headers={"Authorization": f"Bearer {self.token}"})
                assert response.status_code == 406
                assert response.json()['detail']['code'] == 'CAN_NOT_RATE_SESSION_IN_FUTURE'

            with unittest.mock.patch('conferences.controller.conference.now') as mocked_datetime:
                mocked_datetime.return_value = datetime.datetime(2024, 11, 8, 11, 1)
                response = await ac.post(f"/api/sessions/{id_1st_session}/rate", json={'rating': 5},
                                         headers={"Authorization": f"Bearer {self.token}"})

                assert response.status_code == 200


            assert response.json() == {'avg_rate': 5, 'total_rates': 1}

            # ako isti korisnik glasa ponovo desice se samo da se azurira ocena

            with unittest.mock.patch('conferences.controller.conference.now') as mocked_datetime:
                mocked_datetime.return_value = datetime.datetime(2024, 11, 8, 11, 1)
                response = await ac.post(f"/api/sessions/{id_1st_session}/rate", json={'rating': 2},
                                         headers={"Authorization": f"Bearer {self.token}"})

            assert response.status_code == 200
            assert response.json() == {'avg_rate': 2, 'total_rates': 1}

            # ocenu takodje mozemo proveriti uzimanjem konferencije

            response = await ac.get(f"/api/conference?last_updated={self.last_updated}",
                                    headers={"Authorization": f"Bearer {self.token}"})
            assert response.status_code == 200

            res = response.json()

            assert 'ratings' in res
            assert res['ratings'] == {'rates_by_session': {id_1st_session: [2.0, 1]},
                                      'my_rate_by_session': {id_1st_session: 2}}

            # uvecemo drugog korisnika da glasa

            with unittest.mock.patch('conferences.controller.conference.now') as mocked_datetime:
                mocked_datetime.return_value = datetime.datetime(2024, 11, 8, 11, 1)
                response = await ac.post(f"/api/sessions/{id_1st_session}/rate", json={'rating': 5},
                                         headers={"Authorization": f"Bearer {self.token2}"})

            assert response.status_code == 200
            assert response.json() == {'avg_rate': (2 + 5) / 2, 'total_rates': 2}

            # glasace sada i treci korisnik

            with unittest.mock.patch('conferences.controller.conference.now') as mocked_datetime:
                mocked_datetime.return_value = datetime.datetime(2024, 11, 8, 11, 1)
                response = await ac.post(f"/api/sessions/{id_1st_session}/rate", json={'rating': 5},
                                         headers={"Authorization": f"Bearer {self.token3}"})

            assert response.status_code == 200
            assert response.json() == {'avg_rate': (2 + 5 + 5) / 3, 'total_rates': 3}

            # ocenu takodje mozemo proveriti uzimanjem konferencije

            response = await ac.get(f"/api/conference?last_updated={self.last_updated}",
                                    headers={"Authorization": f"Bearer {self.token}"})
            assert response.status_code == 200

            res = response.json()

            assert 'ratings' in res
            assert res['ratings'] == {'my_rate_by_session': {id_1st_session: 2},
                                      'rates_by_session': {id_1st_session: [4.0,
                                                                            3]}}

            # dodacemo i glasanje za drugu sesiju

            id_2nd_session = list(self.sessions.keys())[1]

            with unittest.mock.patch('conferences.controller.conference.now') as mocked_datetime:
                mocked_datetime.return_value = datetime.datetime(2024, 11, 8, 11, 1)
                response = await ac.post(f"/api/sessions/{id_2nd_session}/rate", json={'rating': 1},
                                         headers={"Authorization": f"Bearer {self.token3}"})

            assert response.status_code == 200
            assert response.json() == {'avg_rate': 1, 'total_rates': 1}

            response = await ac.get(f"/api/conference?last_updated={self.last_updated}",
                                    headers={"Authorization": f"Bearer {self.token3}"})
            assert response.status_code == 200

            res = response.json()

            assert 'ratings' in res
            assert res['ratings']['rates_by_session'] == {id_1st_session: [4.0, 3],
                                                          id_2nd_session: [1.0, 1]}

            assert res['ratings']['my_rate_by_session'] == {id_1st_session: 5, id_2nd_session: 1}

            # ukoliko drugi user zahteva isto dobice iste rate ali my rate ce biti razlicit

            response = await ac.get(f"/api/conference?last_updated={self.last_updated}",
                                    headers={"Authorization": f"Bearer {self.token}"})
            assert response.status_code == 200

            res = response.json()
            assert 'ratings' in res
            assert res['ratings']['rates_by_session'] == {id_1st_session: [4.0, 3],
                                                          id_2nd_session: [1.0, 1]}

            assert res['ratings']['my_rate_by_session'] == {id_1st_session: 2}

    async def test_abstract(self):

        nr_abstracts = 0
        for id_session in self.sessions:
            session = self.sessions[id_session]
            assert 'abstract' in session
            if session['abstract']:
                nr_abstracts += 1

        assert nr_abstracts > 0

    async def test_title(self):

        for id_session in self.sessions:
            session = self.sessions[id_session]
            assert 'title' in session
            assert session['title']


    async def do_test_push_notification(self, group_notifications_by_user: bool, expected_notifications: int):
        async with AsyncClient(app=self.app, base_url="http://test") as ac:
            response = await ac.post("/api/authorize")
            assert response.status_code == 200
            token = response.json()['token']

            response = await ac.post('/api/notification-token',
                                     json={'push_notification_token': 'ExponentPushToken[xxxxxxxxxxxxxxxxxxxxx1]'},
                                     headers={"Authorization": f"Bearer {token}"})
            assert response.status_code == 200

            response = await ac.post("/api/authorize")
            assert response.status_code == 200
            token2 = response.json()['token']

            response = await ac.post('/api/notification-token',
                                     json={'push_notification_token': 'ExponentPushToken[xxxxxxxxxxxxxxxxxxxxx2]'},
                                     headers={"Authorization": f"Bearer {token2}"})
            assert response.status_code == 200

            response = await ac.get("/api/me", headers={"Authorization": f"Bearer {token}"})
            assert response.status_code == 200

            response = await ac.get("/api/me", headers={"Authorization": f"Bearer {token2}"})
            assert response.status_code == 200

            id_cra_session = None
            for s in self.sessions:
                session = self.sessions[s]
                if session['title'] == 'Let’s all get over the CRA!':
                    id_cra_session = s
                    break

            assert id_cra_session

            id_eti_session = None
            for s in self.sessions:
                session = self.sessions[s]
                if session['title'] == 'On the ethical challenges raised by robots powered by Artificial Intelligence':
                    id_eti_session = s
                    break

            assert id_eti_session

            response = await ac.post(f"/api/sessions/{id_cra_session}/bookmarks/toggle",
                                     headers={"Authorization": f"Bearer {token}"})
            assert response.status_code == 200
            assert response.json() == {'bookmarked': True}

            response = await ac.post(f"/api/sessions/{id_eti_session}/bookmarks/toggle",
                                     headers={"Authorization": f"Bearer {token}"})
            assert response.status_code == 200
            assert response.json() == {'bookmarked': True}

            response = await ac.post(f"/api/sessions/{id_cra_session}/bookmarks/toggle",
                                     headers={"Authorization": f"Bearer {token2}"})
            assert response.status_code == 200
            assert response.json() == {'bookmarked': True}

            response = await ac.post("/api/import-xml", json={'use_local_xml': True,
                                                              'local_xml_fname': 'sfscon2024.1st_session_moved_for_5_minutes.xml',
                                                              'group_notifications_by_user': group_notifications_by_user
                                                              })
            assert response.status_code == 200

        redis_client = RedisClientHandler.get_redis_client()
        all_messages = redis_client.get_all_messages('opencon_push_notification')
        assert len(all_messages) == expected_notifications
        ...

    @patch.object(RedisClientHandler, "get_redis_client",
                  return_value=RedisClientHandler(redis_instance=fakeredis.FakeStrictRedis()))
    async def test_push_notification_ungrouped(self, *args, **kwargs):
        await self.do_test_push_notification(group_notifications_by_user=False, expected_notifications=3)

    @patch.object(RedisClientHandler, "get_redis_client",
                  return_value=RedisClientHandler(redis_instance=fakeredis.FakeStrictRedis()))
    async def test_push_notification_grouped(self, *args, **kwargs):
        await self.do_test_push_notification(group_notifications_by_user=True, expected_notifications=2)


class TestUpdateXML(BaseAPITest):
    async def setup(self):

        self.import_modules(['src.conferences.api'])

        async with AsyncClient(app=self.app, base_url="http://test") as ac:
            response = await ac.post("/api/import-xml", json={'use_local_xml': True,                                                              'local_xml_fname': 'sfscon2024.xml',
                                                              })
            assert response.status_code == 200

            self.token = (await ac.post('/api/authorize')).json()['token']

            response = await ac.post('/api/notification-token',
                                     json={'push_notification_token': 'ExponentPushToken[xxxxxxxxxxxxxxxxxxxxx2]'},
                                     headers={"Authorization": f"Bearer {self.token}"})
            assert response.status_code == 200


            response = await ac.get('/api/conference', headers={'Authorization': f'Bearer {self.token}'})
            assert response.status_code == 200

            self.sessions = response.json()['conference']['db']['sessions']


    @patch.object(RedisClientHandler, "get_redis_client",
                  return_value=RedisClientHandler(redis_instance=fakeredis.FakeStrictRedis()))
    async def test_removing_session(self, *args, **kwargs):

        async with AsyncClient(app=self.app, base_url="http://test") as ac:

            for session in self.sessions:
                if self.sessions[session]['unique_id'] == '2024day1event95':
                    id_session = self.sessions[session]['id']
                    break

            assert id_session

            response = await ac.post(f"/api/sessions/{id_session}/bookmarks/toggle",
                                     headers={"Authorization": f"Bearer {self.token}"})

            assert response.status_code==200


            response = await ac.post("/api/import-xml", json={'use_local_xml': True, 'local_xml_fname': 'sfscon2024.session-removed.xml',
                                                          })
            assert response.status_code == 200

            response = await ac.get('/api/conference', headers={'Authorization': f'Bearer {self.token}'})
            assert response.status_code == 200
            after_update_sessions = response.json()['conference']['db']['sessions']

            assert len(after_update_sessions) == len(self.sessions) - 1

            redis_client = RedisClientHandler.get_redis_client()
            all_messages = redis_client.get_all_messages('opencon_push_notification')

            ...
            assert len(all_messages) == 1


            # # return removed ecvent
            #
            # response = await ac.post("/api/import-xml", json={'use_local_xml': True, 'local_xml_fname': 'sfscon2024.xml',
            #                                               })
            # assert response.status_code == 200
            #
            # response = await ac.get('/api/conference', headers={'Authorization': f'Bearer {self.token}'})
            # assert response.status_code == 200
            # after_update_sessions = response.json()['conference']['db']['sessions']
            #
            # assert len(after_update_sessions) == len(self.sessions)


class TestJsonData(BaseAPITest):
    async def setup(self):

        current_file_path = os.path.dirname(os.path.realpath(__file__))
        with open(current_file_path + '/assets/sfs2024.10.14.json', 'r') as f:
            self.data = json.load(f)
        assert self.data

        assert 'day' in self.data
        self.sessions = []
        for day in self.data['day']:
            assert 'room' in day
            assert isinstance(day['room'], list)
            for room in day['room']:
                assert 'event' in room
                assert isinstance(room['event'], list) or isinstance(room['event'], dict)

                if isinstance(room['event'], list):
                    for event in room['event']:
                        self.sessions.append(event)
                else:
                    self.sessions.append(room['event'])

    async def test(self):
        unique_ids = set()

        for session in self.sessions:
            if '@unique_id' not in session:
                continue
            if session['@unique_id'] in unique_ids:
                assert False, f'DUPLICATE: {session["title"]}'

            unique_ids.add(session['@unique_id'])


class TestAdmin(BaseAPITest):

    async def setup(self):
        self.import_modules(['src.conferences.api'])

        async with AsyncClient(app=self.app, base_url="http://test") as ac:
            response = await ac.post("/api/import-xml", json={'use_local_xml': True})
            assert response.status_code == 200

            self.token1 = (await ac.post('/api/authorize')).json()['token']
            self.token2 = (await ac.post('/api/authorize')).json()['token']
            self.token3 = (await ac.post('/api/authorize')).json()['token']



            response = await ac.get('/api/conference', headers={'Authorization': f'Bearer {self.token1}'})
            assert response.status_code == 200

            self.sessions = response.json()['conference']['db']['sessions']

    async def test_login_admin(self):
        async with AsyncClient(app=self.app, base_url="http://test") as ac:
            ...
            response = await ac.post("/api/admin/login", json={"username": "admin", "password": "123"})
            assert response.status_code == 401

            response = await ac.post("/api/admin/login", json={"username": "admin", "password": "admin"})
            assert response.status_code == 200

    async def test_get_all_users_with_bookmarks(self):
        async with AsyncClient(app=self.app, base_url="http://test") as ac:

            response = await ac.get("/api/admin/users")
            assert response.status_code == 401

            response = await ac.post("/api/admin/login", json={"username": "admin", "password": "admin"})
            assert response.status_code == 200

            admin_token = response.json()['token']

            response = await ac.get("/api/admin/users", headers={"Authorization": f"Bearer {self.token1}"})
            assert response.status_code == 401

            response = await ac.get("/api/admin/users", headers={"Authorization": f"Bearer {admin_token}"})
            assert response.status_code == 200

            res = response.json()
            assert 'data' in res

            assert 3 == len(res['data'])

            for i in range(3):
                assert res['data'][i]['bookmarks'] == 0

            id_1st_session = None
            for s in self.sessions:
                session = self.sessions[s]
                if session['title'] == 'Let’s all get over the CRA!':
                    id_1st_session = s
                    break

            assert id_1st_session

            response = await ac.post(f"/api/sessions/{id_1st_session}/bookmarks/toggle",
                                     headers={"Authorization": f"Bearer {self.token1}"})

            assert response.status_code == 200


            response = await ac.get("/api/admin/users", headers={"Authorization": f"Bearer {admin_token}"})
            assert response.status_code == 200

            res = response.json()
            assert 'data' in res

            assert 3 == len(res['data'])

            # for i in range(3):
            #     assert res['data'][i]['bookmarks'] == []

            response = await ac.get("/api/admin/users?csv=true", headers={"Authorization": f"Bearer {admin_token}"})
            ...



    async def test_get_sessions_by_rate(self):
        async with AsyncClient(app=self.app, base_url="http://test") as ac:

            response = await ac.post("/api/admin/login", json={"username": "admin", "password": "admin"})

            assert response.status_code == 200
            admin_token = response.json()['token']

            id_1st_session = None
            for s in self.sessions:
                session = self.sessions[s]
                if session['title'] == 'Let’s all get over the CRA!':
                    id_1st_session = s
                    break

            assert id_1st_session

            with unittest.mock.patch('conferences.controller.conference.now') as mocked_datetime:
                mocked_datetime.return_value = datetime.datetime(2024, 11, 1, 11, 0)

                response = await ac.post(f"/api/sessions/{id_1st_session}/rate", json={'rating': 5},
                                         headers={"Authorization": f"Bearer {self.token1}"})

                assert response.status_code == 406
                assert response.json() == {'detail': {"code": "CAN_NOT_RATE_SESSION_IN_FUTURE",
                                        "message": "Rating is only possible after the talk has started."}}


            response = await ac.get('/api/admin/sessions', headers={'Authorization': f'Bearer {admin_token}'})
            assert response.status_code == 200

            assert 'data' in response.json()
            assert len(response.json()['data']) > 10

