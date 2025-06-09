
- Optional login with your Telegram account
TG_API_ID=<your api_id>
TG_API_HASH=<your api_hash>
3. Install dependencies:

4. Run the development server:

## Features

- Register and login with a username and password

- Messages stored locally in `chat.db`
- ChatGPT integration for advice or auto responses
- Chat analytics page showing message counts
- "Auto reply" button to let ChatGPT generate a response

## Setup


1. Get an OpenAI API key.
2. Create a `.env` file with the following contents:

```
FLASK_SECRET=change_me
=======
1. Create a Telegram bot and obtain its **bot token** and **username**.
2. Get an OpenAI API key.
3. Create a `.env` file with the following contents:

```

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

This is a simplified demo and does not replicate all production chat features. It stores data in a local SQLite database and does not support groups.
