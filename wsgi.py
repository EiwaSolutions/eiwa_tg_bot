import os
import threading
from urllib import parse
from bot.plugin_manager import PluginManager

import telegram
from dotenv import load_dotenv
from flask import Flask, jsonify, request
from waitress import serve
from bot.openai_helper import OpenAIHelper, default_max_tokens, are_functions_available
from bot.main import ChatGPTTelegramBot
from runasync import run_async

load_dotenv()

OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
WEB_HOOK = os.environ["WEB_HOOK"]
PORT = os.environ["PORT"]

app = Flask(__name__)

model = os.environ.get("OPENAI_MODEL", "gpt-3.5-turbo")
functions_available = are_functions_available(model=model)
max_tokens_default = default_max_tokens(model=model)

openai_config = {
    "api_key": os.environ["OPENAI_API_KEY"],
    "show_usage": os.environ.get("SHOW_USAGE", "false").lower() == "true",
    "stream": os.environ.get("STREAM", "true").lower() == "true",
    "proxy": os.environ.get("PROXY", None),
    "max_history_size": int(os.environ.get("MAX_HISTORY_SIZE", 15)),
    "max_conversation_age_minutes": int(
        os.environ.get("MAX_CONVERSATION_AGE_MINUTES", 180)
    ),
    "assistant_prompt": os.environ.get(
        "ASSISTANT_PROMPT", "You are a helpful assistant."
    ),
    "max_tokens": int(os.environ.get("MAX_TOKENS", max_tokens_default)),
    "n_choices": int(os.environ.get("N_CHOICES", 1)),
    "temperature": float(os.environ.get("TEMPERATURE", 1.0)),
    "image_size": os.environ.get("IMAGE_SIZE", "512x512"),
    "model": model,
    "enable_functions": os.environ.get(
        "ENABLE_FUNCTIONS", str(functions_available)
    ).lower()
    == "true",
    "functions_max_consecutive_calls": int(
        os.environ.get("FUNCTIONS_MAX_CONSECUTIVE_CALLS", 10)
    ),
    "presence_penalty": float(os.environ.get("PRESENCE_PENALTY", 0.0)),
    "frequency_penalty": float(os.environ.get("FREQUENCY_PENALTY", 0.0)),
    "bot_language": os.environ.get("BOT_LANGUAGE", "en"),
    "show_plugins_used": os.environ.get("SHOW_PLUGINS_USED", "false").lower() == "true",
    "whisper_prompt": os.environ.get("WHISPER_PROMPT", ""),
}

telegram_config = {
    "token": os.environ["TELEGRAM_BOT_TOKEN"],
    "admin_user_ids": os.environ.get("ADMIN_USER_IDS", "-"),
    "allowed_user_ids": os.environ.get("ALLOWED_TELEGRAM_USER_IDS", "*"),
    "enable_quoting": os.environ.get("ENABLE_QUOTING", "true").lower() == "true",
    "enable_image_generation": os.environ.get("ENABLE_IMAGE_GENERATION", "true").lower()
    == "true",
    "enable_transcription": os.environ.get("ENABLE_TRANSCRIPTION", "true").lower()
    == "true",
    "budget_period": os.environ.get("BUDGET_PERIOD", "monthly").lower(),
    "user_budgets": os.environ.get(
        "USER_BUDGETS", os.environ.get("MONTHLY_USER_BUDGETS", "*")
    ),
    "guest_budget": float(
        os.environ.get("GUEST_BUDGET", os.environ.get("MONTHLY_GUEST_BUDGET", "100.0"))
    ),
    "stream": os.environ.get("STREAM", "true").lower() == "true",
    "proxy": os.environ.get("PROXY", None),
    "voice_reply_transcript": os.environ.get(
        "VOICE_REPLY_WITH_TRANSCRIPT_ONLY", "false"
    ).lower()
    == "true",
    "voice_reply_prompts": os.environ.get("VOICE_REPLY_PROMPTS", "").split(";"),
    "ignore_group_transcriptions": os.environ.get(
        "IGNORE_GROUP_TRANSCRIPTIONS", "true"
    ).lower()
    == "true",
    "group_trigger_keyword": os.environ.get("GROUP_TRIGGER_KEYWORD", ""),
    "token_price": float(os.environ.get("TOKEN_PRICE", 0.002)),
    "image_prices": [
        float(i) for i in os.environ.get("IMAGE_PRICES", "0.016,0.018,0.02").split(",")
    ],
    "transcription_price": float(os.environ.get("TRANSCRIPTION_PRICE", 0.006)),
    "bot_language": os.environ.get("BOT_LANGUAGE", "en"),
}

plugin_config = {"plugins": os.environ.get("PLUGINS", "").split(",")}

# Setup and run ChatGPT and Telegram bot
plugin_manager = PluginManager(config=plugin_config)
openai_helper = OpenAIHelper(config=openai_config, plugin_manager=plugin_manager)

bot_instance = ChatGPTTelegramBot(config=telegram_config, openai=openai_helper)
application = bot_instance.run()


@app.route("/", methods=["GET"])
def hello():
    print("", end="")
    return "Bot has connected!"


@app.route(rf"/{BOT_TOKEN}".format(), methods=["POST"])
async def respond():
    update = telegram.Update.de_json(request.get_json(force=True), application.bot)
    run_async(application.initialize())
    thread = threading.Thread(
        target=run_async, args=(application.process_update(update),)
    )
    thread.start()
    return jsonify({"status": "success", "message": "Received message successfully."})


@app.route("/setwebhook", methods=["GET", "POST"])
async def configure_webhook():
    webhookUrl = parse.urljoin(WEB_HOOK, rf"/{BOT_TOKEN}")
    result = await application.bot.setWebhook(webhookUrl)
    if result:
        print(rf"webhook configured: {webhookUrl}")
        return rf"webhook configured: {webhookUrl}"
    else:
        print("webhook setup failed")
        return "webhook setup failed"


if __name__ == "__main__":
    run_async(configure_webhook())
    serve(app, host="0.0.0.0", port=PORT)
