# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2023 Digital CUBE <https://digitalcube.rs>

import os

import dotenv

current_file_dir = os.path.dirname(os.path.abspath(__file__))

try:
    dotenv.load_dotenv(current_file_dir + "/../.env")
except Exceptio as e:
    pass
    
DB_CONFIG = {
    "connections": {
        "default": f"postgres://"
                   f"{os.getenv('DB_USERNAME')}:{os.getenv('DB_PASSWORD')}@"
                   f"{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
    },
    "apps": {
        "models": {
            "models": ["conferences.models" , "aerich.models"],
            "default_connection": "default",
        }
    }
}

import pprint
pprint.pprint(DB_CONFIG)