# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2023 Digital CUBE <https://digitalcube.rs>

import hashlib
import json


def calculate_md5_checksum(file_path):
    md5_hash = hashlib.md5()
    with open(file_path, "rb") as f:
        # Read and update hash string value in blocks of 4K
        for byte_block in iter(lambda: f.read(4096), b""):
            md5_hash.update(byte_block)
    return md5_hash.hexdigest()


def calculate_md5_checksum_for_string(string):
    md5_hash = hashlib.md5()
    md5_hash.update(string.encode('utf-8'))
    return md5_hash.hexdigest()


def calculate_md5_checksum_for_dict(d: dict):
    serialized_dict = json.dumps(d, sort_keys=True).encode('utf-8')
    md5_hash = hashlib.md5()
    md5_hash.update(serialized_dict)
    return md5_hash.hexdigest()
