# Telegram ChatGPT Web App

This project is a minimal example of a web application that authenticates users via the Telegram login widget, stores chat history in SQLite and connects to the OpenAI ChatGPT API to generate replies.

## Features

- Login using your Telegram account
- Messages stored locally in `chat.db`
- ChatGPT integration for advice or auto responses
- Chat analytics page showing message counts
- "Auto reply" button to let ChatGPT generate a response

## Setup

1. Create a Telegram bot and obtain its **bot token** and **username**.
2. Get an OpenAI API key.
3. Create a `.env` file with the following contents:

```
FLASK_SECRET=change_me
TELEGRAM_BOT_TOKEN=<your bot token>
TELEGRAM_BOT_USERNAME=<your bot username>
OPENAI_API_KEY=<your OpenAI key>
```

4. Install dependencies:

```bash
pip install -r requirements.txt
```

5. Run the development server:

```bash
python app.py
```

Then open `http://localhost:5000` in your browser.

## Notes

This is a simplified demo and does not replicate all Telegram features. It stores data in a local SQLite database and does not support groups.
