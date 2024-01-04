# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2023 Digital CUBE <https://digitalcube.rs>

import uuid

import pydantic
from typing import Optional

from app import get_app
import conferences.controller as controller

app = get_app()


class FlowRequest(pydantic.BaseModel):
    conference_id: Optional[uuid.UUID]
    pretix_order_id: Optional[str]

    text: str
    data: Optional[dict] = None


@app.post('/api/flows', )
async def add_flow(request: FlowRequest):
    conference = await controller.get_conference(id_conference=request.conference_id) if request.conference_id else None
    pretix_order = await controller.get_pretix_order(conference, request.pretix_order_id) if request.pretix_order_id else None

    return await controller.add_flow(conference, pretix_order, request.text)
