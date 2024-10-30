# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2023 Digital CUBE <https://digitalcube.rs>

import fastapi.exceptions


class AppException(Exception):

    def __init__(self, id_message, message=None, data=None, status_code=400):
        super(AppException, self).__init__(id_message)
        self.id_message = id_message
        self.message = message
        self.data = data
        self.status_code = status_code

    def to_dict(self):
        return {
            'id_message': self.id_message,
            'message': self.message,
            'data': self.data,
            'status_code': self.status_code
        }
