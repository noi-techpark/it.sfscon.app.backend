# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2023 Digital CUBE <https://digitalcube.rs>

import os
import pprint
import uuid
import json

import dotenv
import logging
from httpx import AsyncClient
from base_test_classes import BaseAPITest

os.environ["TEST_MODE"] = "true"

dotenv.load_dotenv()

logging.disable(logging.CRITICAL)


def get_local_xml_content():
    try:
        with open(f'{os.path.dirname(os.path.realpath(__file__))}/assets/sfscon2023.xml', 'r') as f:
            return f.read()
    except Exception as e:
        raise


class TestAPIBasic(BaseAPITest):

    async def setup(self):
        self.import_modules(['src.conferences.api'])

    async def test_get_all_conferences_expect_nothing_to_be_returned(self):
        async with AsyncClient(app=self.app, base_url="http://test") as ac:
            x = await ac.get('/openapi.json')
            assert x.status_code == 200
            response = await ac.get("/api/conferences")
        assert response.status_code == 200
        assert [] == response.json()

    async def test_create_conference_online_conent(self):
        async with AsyncClient(app=self.app, base_url="http://test") as ac:
            response = await ac.post("/api/conferences", json={"default": True})

    async def test_create_conference(self):
        async with AsyncClient(app=self.app, base_url="http://test") as ac:
            response = await ac.post("/api/conferences", json={'xml_content': get_local_xml_content(), 'default': False})

        assert response.status_code == 200
        assert 'id' in response.json()

    async def test_create_and_fetch_conference(self):
        async with AsyncClient(app=self.app, base_url="http://test") as ac:
            response = await ac.post("/api/conferences", json={'xml_content': get_local_xml_content(), 'default': False})

        assert response.status_code == 200
        assert 'id' in response.json()

        id_conference = response.json()['id']

        async with AsyncClient(app=self.app, base_url="http://test") as ac:
            response = await ac.get(f"/api/conferences/{id_conference}")

        assert response.status_code == 200
        assert response.json()['conference']['acronym'] == 'sfscon-2023'

    async def test_register_pretix_user(self):
        async with AsyncClient(app=self.app, base_url="http://test") as ac:
            response = await ac.post("/api/conferences", json={'xml_content': get_local_xml_content(), 'default': False})

        assert response.status_code == 200
        assert 'id' in response.json()

        id_conference = response.json()['id']

        async with AsyncClient(app=self.app, base_url="http://test") as ac:
            response = await ac.get(f"/api/conferences/{id_conference}")

        assert response.status_code == 200
        assert response.json()['conference']['acronym'] == 'sfscon-2023'

        async with AsyncClient(app=self.app, base_url="http://test") as ac:
            response = await ac.post(f"/api/conferences/{id_conference}/pretix",
                                     json={'order': 'DRXSG',
                                           'pushToken': 'ExponentPushToken[xxxxxxxxxxxxxxxxxxxxxx]'}
                                     )
            assert 'id' in response.json()
            assert 'token' in response.json()
            assert 'created' in response.json() and response.json()['created'] is True

    async def test_non_authorized_me(self):
        async with AsyncClient(app=self.app, base_url="http://test") as ac:
            result = await ac.get(f"/api/tenants/me")

        assert result.status_code == 403
        assert result.json() == {'detail': 'UNAUTHORIZED'}


class TestDashboard(BaseAPITest):

    async def setup(self):
        self.import_modules(['src.conferences.api'])

    async def test_dashboard(self):
        async with AsyncClient(app=self.app, base_url="http://test") as ac:
            x = await ac.get('/openapi.json')
            assert x.status_code == 200

            response = await ac.get(f"/api/conferences/sfscon-2023/dashboard")
            assert response.status_code == 200

    async def test_attendees(self):
        async with AsyncClient(app=self.app, base_url="http://test") as ac:
            response = await ac.get(f"/api/conferences/sfscon-2023/attendees")
            assert response.status_code == 200

    async def test_sessions(self):
        async with AsyncClient(app=self.app, base_url="http://test") as ac:
            response = await ac.post("/api/conferences", json={'xml_content': get_local_xml_content(), 'default': False})

        async with AsyncClient(app=self.app, base_url="http://test") as ac:
            response = await ac.get(f"/api/conferences/sfscon-2023/sessions")
            assert response.status_code == 200


class TestAPIWithConferenceAndRegisteredUser(BaseAPITest):

    async def setup(self):
        self.import_modules(['src.conferences.api'])

        async with AsyncClient(app=self.app, base_url="http://test") as ac:
            response = await ac.post("/api/conferences", json={'xml_content': get_local_xml_content(), 'default': False})

        assert response.status_code == 200
        assert 'id' in response.json()

        self.id_conference = response.json()['id']

        async with AsyncClient(app=self.app, base_url="http://test") as ac:
            response = await ac.get(f"/api/conferences/{self.id_conference}")

        assert response.status_code == 200
        assert response.json()['conference']['acronym'] == 'sfscon-2023'

        async with AsyncClient(app=self.app, base_url="http://test") as ac:
            response = await ac.post(f"/api/conferences/{self.id_conference}/pretix",
                                     json={'order': 'DRXSG',
                                           'pushToken': 'ExponentPushToken[xxxxxxxxxxxxxxxxxxxxxx]'}
                                     )
            assert 'id' in response.json()
            assert 'token' in response.json()
            assert 'created' in response.json() and response.json()['created'] is True

            self.token = response.json()['token']

        async with AsyncClient(app=self.app, base_url="http://test") as ac:
            result = await ac.get(f"/api/tenants/me",
                                  headers={"Authorization": f"Bearer {self.token}"})

        assert result.status_code == 200
        assert result.json() == {'id': result.json()['id'], 'data': {'organization': 'Digital Cube DOO', 'pretix_order': 'DRXSG'}, 'email': 'ivo@digitalcube.rs', 'first_name': 'Ivo',
                                 'last_name': 'Kovačević'}

    async def test_get_conference_csv(self):
        async with AsyncClient(app=self.app, base_url="http://test") as ac:
            response = await ac.get(f"/api/conferences/sfscon-2023/talks.csv")
            assert response.status_code == 200

            response = await ac.get(f"/api/conferences/sfscon-2023/attendees.csv")
            assert response.status_code == 200
        ...

    async def test_push_flow(self):
        async with AsyncClient(app=self.app, base_url="http://test") as ac:
            result = await ac.post(f"/api/flows",
                                   json={'conference_id': self.id_conference,
                                         'pretix_order_id': 'DRXSG',
                                         'text': 'some text'},
                                   headers={"X-Api-Key": f"{os.getenv('PRINTER_X_API_KEY')}"})
            ...

    async def test_rate_event(self):

        async with AsyncClient(app=self.app, base_url="http://test") as ac:
            serialized = await ac.get(f"/api/conferences/{self.id_conference}")

            id_session = serialized.json()['conference']['idx']['ordered_sessions_by_days']['2023-11-10'][5]

            assert id_session is not None

            result = await ac.post(f"/api/conferences/sessions/{id_session}/rate",
                                   json={'rate': 5},
                                   headers={"Authorization": f"Bearer {self.token}"})

            assert result.status_code == 200
            assert result.json()['avg'] == 5.0

    async def test_bookmark_event(self):

        async with AsyncClient(app=self.app, base_url="http://test") as ac:
            serialized = await ac.get(f"/api/conferences/{self.id_conference}")

            result = await ac.get(f"/api/conferences/{self.id_conference}/bookmarks",
                                  headers={"Authorization": f"Bearer {self.token}"})

            assert result.json() == []

            id_session = serialized.json()['conference']['idx']['ordered_sessions_by_days']['2023-11-10'][5]

            assert id_session is not None

            result = await ac.post(f"/api/conferences/sessions/{id_session}/toggle-bookmark",
                                   headers={"Authorization": f"Bearer {self.token}"})

            assert result.status_code == 200
            assert result.json()['bookmarked'] is True

            result = await ac.get(f"/api/conferences/{self.id_conference}/bookmarks",
                                  headers={"Authorization": f"Bearer {self.token}"})

            assert result.json() == [id_session]

            result = await ac.post(f"/api/conferences/sessions/{id_session}/toggle-bookmark",
                                   headers={"Authorization": f"Bearer {self.token}"})

            assert result.status_code == 200
            assert result.json()['bookmarked'] is False

            result = await ac.get(f"/api/conferences/{self.id_conference}/bookmarks",
                                  headers={"Authorization": f"Bearer {self.token}"})

            assert result.json() == []

    async def test_bookmark_non_existing_event(self):

        async with AsyncClient(app=self.app, base_url="http://test") as ac:
            id_session = uuid.uuid4()
            exp = None
            try:
                await ac.post(f"/api/conferences/sessions/{id_session}/toggle-bookmark",
                              headers={"Authorization": f"Bearer {self.token}"})
            except Exception as e:
                exp = e

            assert str(exp) == 'EVENT_SESSION_NOT_FOUND'

    #
    async def test_push_notification(self):
        async with AsyncClient(app=self.app, base_url="http://test") as ac:
            res = await ac.post(f'/api/conferences/pretix_orders/DRXSG/test_push_notification',
                                json={'subject': 'test', 'message': 'test123'})
            assert res.status_code == 200

    async def test_register_printer(self):

        lanes = os.getenv('CHECKIN_LANES', None)
        assert lanes is not None

        lanes = json.loads(lanes)
        lane1 = lanes['LANE-DC']
        printer_x_api_key = os.getenv('PRINTER_X_API_KEY', None)

        async with AsyncClient(app=self.app, base_url="http://test") as ac:
            res = await ac.post(f'/api/printers/register/{lane1}',
                                headers={'X-Api-Key': printer_x_api_key,
                                         'Content-Type': 'application/json'})

            assert res.status_code == 200

    async def test_scan_pretix_qr_code(self):

        printer_response_payload = '''
        {
            "count": 1,
            "next": null,
            "previous": null,
            "results": [
                {
                    "id": 23879610,
                    "order": "DRXSG",
                    "positionid": 1,
                    "item": 405843,
                    "variation": null,
                    "price": "0.00",
                    "attendee_name": "Ivo Kovačević",
                    "attendee_name_parts": {
                        "_scheme": "given_family",
                        "given_name": "Ivo",
                        "family_name": "Kovačević"
                    },
                    "company": "Digital Cube DOO",
                    "street": null,
                    "zipcode": null,
                    "city": null,
                    "country": null,
                    "state": null,
                    "attendee_email": "ivo@digitalcube.rs",
                    "voucher": null,
                    "tax_rate": "0.00",
                    "tax_value": "0.00",
                    "secret": "d8cpm24fyuv2nn73zasrzgbcynfcfxd3",
                    "addon_to": null,
                    "subevent": 3973986,
                    "checkins": [
                        {
                            "id": 19727648,
                            "datetime": "2023-10-13T15:36:41.601865+02:00",
                            "list": 313919,
                            "auto_checked_in": false,
                            "gate": null,
                            "device": null,
                            "type": "entry"
                        }
                    ],
                    "downloads": [
                        {
                            "output": "pdf",
                            "url": "https://pretix.eu/api/v1/organizers/noi-digital/events/sfscon23/orderpositions/23879610/download/pdf/"
                        },
                        {
                            "output": "passbook",
                            "url": "https://pretix.eu/api/v1/organizers/noi-digital/events/sfscon23/orderpositions/23879610/download/passbook/"
                        }
                    ],
                    "answers": [
                        {
                            "question": 97901,
                            "answer": "NO",
                            "question_identifier": "8DG7LBJE",
                            "options": [
                                161406
                            ],
                            "option_identifiers": [
                                "88MRLUL8"
                            ]
                        }
                    ],
                    "tax_rule": null,
                    "pseudonymization_id": "MB7BUEJKLR",
                    "seat": null,
                    "require_attention": false,
                    "order__status": "p",
                    "valid_from": null,
                    "valid_until": null,
                    "blocked": null
                }
            ]
        }
        '''

        lanes = os.getenv('CHECKIN_LANES', None)
        assert lanes is not None

        lanes = json.loads(lanes)
        lane1 = lanes['LANE1']
        printer_x_api_key = os.getenv('PRINTER_X_API_KEY', None)

        printer_response_payload = json.loads(printer_response_payload)
        secret = printer_response_payload['results'][0]['secret']

        async with AsyncClient(app=self.app, base_url="http://test") as ac:
            res = await ac.post(f'/api/conferences/{self.id_conference}/scans/lanes/{lane1}/{secret}',
                                headers={'X-Api-Key': printer_x_api_key,
                                         'Content-Type': 'application/json'},
                                json={'pretix_response': printer_response_payload})

            assert res.status_code == 200
            ...


    #
    async def test_5minutes_notification_test_only_mode(self):
        async with AsyncClient(app=self.app, base_url="http://test") as ac:
            res = await ac.post(f'/api/conferences/sfscon2023/notify-5-minutes-before-start',
                                json={'now_time': '2023-10-11 08:26:00',
                                      'test_only': True})

            assert res.status_code == 200
            assert 'enqueued_messages' in res.json() and res.json()['enqueued_messages'] == 0
            assert 'test_only' in res.json() and res.json()['test_only'] is True
            # assert res.json() == {'enqueued_messages': 0, 'test_only': True}   # no sessions in next 5 minutes

            serialized = await ac.get(f"/api/conferences/{self.id_conference}")

            serialized = serialized.json()
            id_session = None
            for ie in serialized['conference']['idx']['ordered_sessions_by_days']['2023-11-10']:
                e = serialized['conference']['db']['sessions'][ie]
                if e['unique_id'] == '2023day1event1':
                    id_session = e['id']
                    break

            assert id_session

            res = await ac.post(f"/api/conferences/sessions/{id_session}/toggle-bookmark",
                                   headers={"Authorization": f"Bearer {self.token}"})

            assert res.status_code == 200
            assert res.json() == {'bookmarked': True}

            res = await ac.post(f'/api/conferences/sfscon2023/notify-5-minutes-before-start',
                                json={'now_time': '2023-11-10 08:26:00'})
            assert res.status_code == 200
            # assert res.json() == {'enqueued_messages': 1, 'test_only': True,
            #                       'log': ['Ivo Kovačević <ivo@digitalcube.rs> (Digital Cube DOO): Check-in start at 08:30']
            #                       }


class TestAdminLogin(BaseAPITest):

    async def setup(self):
        self.import_modules(['src.conferences.api'])

    async def test_scan(self):
        async with AsyncClient(app=self.app, base_url="http://test") as ac:
            res = await ac.post(f'/api/conferences/scan',
                                json={'id_target': str(uuid.uuid4()), 'id_location': 'e4041668-8199-48c5-bb00-0b4e7042f479'})

            assert res.status_code == 200
            print(res.json())

    #
    async def deprecated_test_get_attendees(self):
        async with AsyncClient(app=self.app, base_url="http://test") as ac:
            res = await ac.post(f"/api/tenants/sessions",
                                json={'username': os.getenv('ADMIN_USERNAME'),
                                      'password': 'xyz'})

            assert res.status_code == 403
            assert res.json() == {'detail': 'UNAUTHORIZED'}

            res = await ac.post(f"/api/tenants/sessions",
                                json={'username': os.getenv('ADMIN_USERNAME'),
                                      'password': os.getenv('ADMIN_PASSWORD')})

            assert res.status_code == 200
            assert 'token' in res.json()

            token = res.json()['token']

            res = await ac.get(f'/api/tenants/me',
                               headers={"Authorization": f"Bearer {token}"})

            assert res.status_code == 200
            assert res.json()['first_name'] == os.getenv('ADMIN_USERNAME')

            res = await ac.get(f'/api/conferences/sfs2023/attendees?page=2&per_page=3&search=',
                               headers={"Authorization": f"Bearer {token}"})

            assert res.status_code == 200

            assert res.json()['summary'] == {"total_items": 335,
                                             "total_pages": 112,
                                             "page": 2,
                                             "per_page": 3,
                                             "previous_page": 1,
                                             "next_page": 3
                                             }

            assert res.json()['header'] == [{'name': 'First Name', 'key': 'first_name', 'width': '100px'}, {'name': 'Last Name', 'key': 'last_name', 'width': '100px'},
                                            {'name': 'Organization', 'key': 'organization', 'width': '100px'}, {'name': 'Email', 'key': 'email', 'width': '100px'},
                                            {'name': 'Pretix Order', 'key': 'pretix_order', 'width': '100px'}, {'name': 'Has SFSCON app', 'key': 'has_app', 'width': '100px'}]
            assert len(res.json()['data']) == 3

            res = await ac.get(f'/api/conferences/sfs2023/attendees?page=2&per_page=3&search=@example.net',
                               headers={"Authorization": f"Bearer {token}"})

            assert res.status_code == 200
            assert res.json()['summary'] == {"total_items": 97,
                                             "total_pages": 33,
                                             "page": 2,
                                             "per_page": 3,
                                             "previous_page": 1,
                                             "next_page": 3
                                             }
            # print(json.dumps(res.json()['data'], indent=4))
            # print(json.dumps(res.json()['summary'], indent=4))

            return
            res = await ac.post(f"/api/tenants/sessions",
                                json={'username': os.getenv('LANE_USERNAME_PREFIX', 'lane') + '1',
                                      'password': os.getenv('LANE_USER_PASSWORD')})
            assert res.status_code == 200
            token = res.json()['token']

            res = await ac.get(f'/api/tenants/me', headers={"Authorization": f"Bearer {token}"})

            assert res.status_code == 200

            ...
