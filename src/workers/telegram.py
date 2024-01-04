# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2023 Digital CUBE <https://digitalcube.rs>

import os
import redis
import httpx
import dotenv
import asyncio

dotenv.load_dotenv()


async def read_redis_queue(queue_name):
    redis_host = os.getenv('REDIS_SERVER')
    redis_client = redis.Redis(host=redis_host, port=6379, db=0)
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    bot_chatIDS = os.getenv('TELEGRAM_CHAT_ID')
    send_url = f'https://api.telegram.org/bot{bot_token}/sendMessage'

    def send_message(data):
        response = httpx.post(send_url, data=data)
        return response.json()

    while True:
        res = redis_client.blpop(queue_name.encode('utf-8'),60*5)
        if not res:
            print('.')
            continue
        
        queue, item = res
        
        item = item.decode('utf-8')

        plain_text = item.split('|||')[-1].strip()

        for bot_chatID in bot_chatIDS.split(','):
            data = {
                'chat_id': bot_chatID,
                'text': plain_text
            }

            send_message(data)


if __name__ == "__main__":
    queue_name = "log_list"
    asyncio.run(read_redis_queue(queue_name))