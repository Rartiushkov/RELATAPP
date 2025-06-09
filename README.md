
# ChatGPT Web App

This project is a minimal example of a web application that allows users to chat with Telegram contacts or with a local account. Chats are stored in SQLite and the app connects to the OpenAI ChatGPT API to generate replies.


## Features



## Features

- Register and login with a username and password


- Optional login with your Telegram account using SMS code
- Browse your Telegram dialogs (chats only, no groups)
- Messages stored locally in `chat.db`
- ChatGPT integration for advice or auto responses
- Chat analytics page showing message counts
- "Auto reply" button to let ChatGPT generate and send a reply

## Setup


1. Get an OpenAI API key.
2. Create a `.env` file with the following contents. The Telegram values are
   required if you want to log in via Telegram:

```
FLASK_SECRET=change_me

OPENAI_API_KEY=<your OpenAI key>
TG_API_ID=<your api_id>
TG_API_HASH=<your api_hash>
```


If you omit `TG_API_ID` or `TG_API_HASH`, the "Login with Telegram" option will
not be shown.

3. Install dependencies:


```bash
pip install -r requirements.txt
```


4. Run the development server:


```bash
python app.py
```

Then open `http://localhost:5000` in your browser.


After Telegram login you will see a list of your private chats. Select one to load messages and chat with the Auto reply button.

## Notes

This is a simplified demo and does not replicate all production chat features. It stores data in a local SQLite database and does not support groups.
