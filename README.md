# Telegram Affiliate Bot with Hybrid ID Validation for Pocket Option

Telegram bot that validates users based on their Pocket Option ID by searching for postback messages in a specific Telegram channel.

## Features

- User verification via Pocket Option ID
- Hybrid validation: local cache + deep channel search
- Real-time channel monitoring for new IDs
- SQLite database for persistent storage
- Clean Russian language interface

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Create `.env` file from `.env.example`:
```bash
cp .env.example .env
```

3. Create `.env` file with the following variables:
```
BOT_TOKEN=your_telegram_bot_token_here
API_ID=your_telegram_api_id_here
API_HASH=your_telegram_api_hash_here
WEB_APP_URL=https://your-web-app-url.com
```

Where to get credentials:
- `BOT_TOKEN`: Get from [@BotFather](https://t.me/BotFather)
- `API_ID` and `API_HASH`: Get from [my.telegram.org](https://my.telegram.org)
- `WEB_APP_URL`: Your Telegram Web App URL (optional, defaults to placeholder)

4. Run the bot:
```bash
python bot.py
```

## Usage

1. Start the bot with `/start`
2. If not verified, enter your Pocket Option ID
3. The bot will validate your ID and grant access to the Trading HUD

## Database Schema

- `verified_users`: Stores verified user bindings (tg_id, pocket_id)
- `cache_ids`: Stores all recognized Pocket Option IDs from the channel
