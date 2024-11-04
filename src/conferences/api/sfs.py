# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2023 Digital CUBE <https://digitalcube.rs>
import datetime
import os
import uuid
from typing import Optional, Union

import jwt
import pydantic
from fastapi import HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware

import conferences.controller as controller
import conferences.models as models
from app import get_app
from conferences.controller import ConferenceImportRequestResponse

app = get_app()

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer


class PushNotificationRequest(pydantic.BaseModel):
    push_notification_token: Optional[Union[None, str]] = Query(default=None)

async def verify_admin_token(token):
    try:
        JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY')
        decoded = jwt.decode(token, JWT_SECRET_KEY, algorithms=['HS256'])
        if decoded and 'username' in decoded and decoded['username'] == 'admin':
            return decoded

        raise HTTPException(status_code=401, detail={"code": "INVALID_TOKEN", "message": "Invalid token"})
    except Exception as e:
        raise HTTPException(status_code=401, detail={"code": "INVALID_TOKEN", "message": "Invalid token"})

async def verify_token(token):
    try:
        JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY')
        decoded = jwt.decode(token, JWT_SECRET_KEY, algorithms=['HS256'])

        user = await controller.get_user(decoded['id_user'])
        if not user:
            raise HTTPException(status_code=401,
                                detail={"code": "INVALID_TOKEN", "message": "Invalid token, user not found"})

        return decoded
    except Exception as e:
        raise HTTPException(status_code=401, detail={"code": "INVALID_TOKEN", "message": "Invalid token"})




oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/authorize")

oauth2_scheme_admin = OAuth2PasswordBearer(tokenUrl="/api/admin/login")

origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
)


@app.get('/api/authorize')
async def create_authorization(push_notification_token: Optional[str] = Query(default=None)):
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'secret')

    id_user = await controller.authorize_user(push_notification_token)

    payload = {
        'id_user': id_user,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(days=2 * 365),
    }

    encoded_jwt = jwt.encode(payload, JWT_SECRET_KEY, algorithm='HS256')

    return {'token': encoded_jwt}


@app.post('/api/authorize')
async def create_authorization_post():
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'secret')

    id_user = await controller.authorize_user()

    payload = {
        'id_user': id_user,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(days=2 * 365),
    }

    encoded_jwt = jwt.encode(payload, JWT_SECRET_KEY, algorithm='HS256')

    return {'token': encoded_jwt}


@app.post('/api/notification-token')
async def store_notification_token(request: PushNotificationRequest, token: str = Depends(oauth2_scheme)):
    decoded = await verify_token(token)
    user = await controller.get_user(decoded['id_user'])
    user.push_notification_token = request.push_notification_token
    await user.save()


@app.get('/api/me')
async def get_me(token: str = Depends(oauth2_scheme)):
    return await verify_token(token)


class ImportConferenceRequest(pydantic.BaseModel):
    # use_local_xml: Optional[Union[bool, None]] = False
    use_local_xml: Optional[bool] = False
    local_xml_fname: Optional[str] = 'sfscon2024.xml'
    group_notifications_by_user: Optional[bool] = True

@app.post('/api/admin/import-xml', response_model=ConferenceImportRequestResponse,)
async def admin_import_conference_xml_api( request: ImportConferenceRequest = None, token: str = Depends(oauth2_scheme_admin)):
    await verify_admin_token(token)

    if request is None:
        request = ImportConferenceRequest()

    return await controller.do_import_xml(request)



@app.post('/api/import-xml', response_model=ConferenceImportRequestResponse, )
async def import_conference_xml_api(_request: Request, request: ImportConferenceRequest = None):

    if  _request.client.host not in ('localhost', '127.0.0.1', '::1'):
        raise HTTPException(status_code=401, detail={"code": "INVALID_HOST", "message": "Invalid host"})

    if request is None:
        request = ImportConferenceRequest()

    return await controller.do_import_xml(request)



@app.get('/api/conference')
async def get_current_conference(last_updated: Optional[str] = Query(default=None),
                                 token: str = Depends(oauth2_scheme)):
    # return verify_token(token)

    decoded = await verify_token(token)
    return await controller.opencon_serialize_anonymous(decoded['id_user'], await controller.get_current_conference(),
                                                         last_updated=last_updated)


@app.get('/api/conference/static')
async def get_current_conference_static(_request: Request):
    if  _request.client.host not in ('localhost', '127.0.0.1', '::1'):
        raise HTTPException(status_code=401, detail={"code": "INVALID_HOST", "message": "Invalid host"})

    return await controller.opencon_serialize_static(await controller.get_current_conference())



class RateRequest(pydantic.BaseModel):
    rating: int


@app.post('/api/sessions/{id_session}/rate')
async def rate_session(id_session: uuid.UUID, request: RateRequest, token: str = Depends(oauth2_scheme)):
    decoded = await  verify_token(token)
    return await controller.rate_session(id_user=decoded['id_user'], id_session=id_session, rate=request.rating)


@app.post('/api/sessions/{id_session}/bookmarks/toggle')
async def toggle_bookmark_for_session(id_session: uuid.UUID, token: str = Depends(oauth2_scheme)):
    decoded = await verify_token(token)
    return await controller.bookmark_session(id_user=decoded['id_user'], id_session=id_session)


class AdminLoginRequest(pydantic.BaseModel):
    username: str
    password: str


@app.post('/api/admin/login')
async def login_admin(request: AdminLoginRequest):
    if (request.username, request.password) != (os.getenv('ADMIN_USERNAME'), os.getenv('ADMIN_PASSWORD')):
        raise HTTPException(status_code=401,
                            detail={"code": "INVALID_ADMIN_USERNAME_OR_PASSWORD",
                                    "message": "Invalid admin username or password"})

    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'secret')

    payload = {
        'username': 'admin',
        'exp': datetime.datetime.utcnow() + datetime.timedelta(days=2),
    }

    encoded_jwt = jwt.encode(payload, JWT_SECRET_KEY, algorithm='HS256')

    return {'token': encoded_jwt}


@app.get('/api/admin/dashboard')
async def get_dashboard():
    return await controller.get_dashboard()

@app.get('/api/admin/users')
async def get_users_with_bookmarks(
        csv: Optional[bool] = False,
        order_field: Optional[str] = None,
        order_direction: Optional[models.SortOrder] = None,
        token: str = Depends(oauth2_scheme_admin)):
    await verify_admin_token(token)
    if csv:
        return await controller.csv_users()

    return {'data': await controller.get_all_anonymous_users_with_bookmarked_sessions(order_field, order_direction)}


@app.get('/api/admin/sessions')
async def get_sessions_by_rate(
        csv: Optional[bool] = False,
        order_field: Optional[str] = None,
        order_direction: Optional[models.SortOrder] = None,
        token: str = Depends(oauth2_scheme_admin)):
    await verify_admin_token(token)
    if csv:
        return await controller.csv_sessions()
    return {'data': await controller.get_sessions_by_rate(order_field, order_direction)}


@app.get('/api/admin/summary')
async def get_event_summary(token: str = Depends(oauth2_scheme_admin)):
    await verify_admin_token(token)
    return await controller.get_event_summary()