# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2023 Digital CUBE <https://digitalcube.rs>

import httpx
import os
import dotenv

from dotenv import load_dotenv

load_dotenv()

# Replace 'YOUR_BOT_TOKEN' with your actual bot token received from BotFather
bot_token = os.getenv('TELEGRAM_BOT_TOKEN')

print(bot_token)

# Telegram API URL for getting updates
get_updates_url = f'https://api.telegram.org/bot{bot_token}/getUpdates'

# Function to get the chat ID from the latest message
def get_chat_id():
    response = httpx.get(get_updates_url)
    updates = response.json()

    # Check if there are any new updates
    if updates['result']:
        # Get the last update
        last_update = updates['result'][-1]
        # Extract the chat ID
        chat_id = last_update['message']['chat']['id']
        print(last_update)
        return chat_id
    else:
        return "No new messages."

# Call the function and print the chat ID
chat_id = get_chat_id()
print(f"The chat ID is: {chat_id}")

