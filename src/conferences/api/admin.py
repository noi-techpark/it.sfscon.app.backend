# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2023 Digital CUBE <https://digitalcube.rs>

import pydantic

from app import get_app
import conferences.controller as controller

app = get_app()


@app.get('/api/conferences/{conference_acronym}/dashboard', )
async def get_conference_dashboard(conference_acronym: str):
    return await controller.get_dashboard(acronym=conference_acronym)


@app.get('/api/conferences/{conference_acronym}/attendees')
async def get_conference_attendees(conference_acronym: str, page: int = 1, per_page: int = 7, search: str = None):
    return await controller.get_conference_attendees(conference_acronym=conference_acronym, page=page, per_page=per_page, search=search)


@app.get('/api/conferences/{conference_acronym}/sessions')
async def get_conference_sessions(conference_acronym: str):
    return await controller.get_conference_sessions(conference_acronym=conference_acronym)


class TestNotificationRequest(pydantic.BaseModel):
    subject: str
    message: str


@app.post('/api/conferences/pretix_orders/{id_pretix_order}/test_push_notification')
async def test_push_notification(id_pretix_order: str, request: TestNotificationRequest):
    try:
        conference = await controller.get_conference_by_acronym(acronym='sfscon2023')

        pretix_order = await controller.get_pretix_order(conference=conference, id_pretix_order=id_pretix_order)
        res = await controller.enqueue_notification(pretix_order=pretix_order, subject=request.subject, message=request.message)
    except Exception as e:
        raise e
    return res
