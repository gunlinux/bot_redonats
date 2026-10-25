import os
from dotenv import load_dotenv

load_dotenv()


# redis

rabbit_url: str = os.environ.get('RABBIT_URL', 'amqp://user:password@localhost:5672/')
rabbit_vhost: str = os.environ.get('RABBIT_VHOST', 'gunlinux_bot')

# Incoming donation alerts (second RabbitMQ, vhost in URL path)
rabbit_alerts: str = os.environ.get('RABBIT_ALERTS', rabbit_url)

# Beer consumer
BEER_URL: str = os.environ.get('BEER_URL', 'http://127.0.0.1:6016/donate')

# Retwitch
RECLIENT_ID: str = os.environ.get('RECLIENT_ID', '')
RECLIENT_SECRET: str = os.environ.get('RECLIENT_SECRET', '')
REOWNER_ID: str = os.environ.get('REOWNER_ID', '')
REBOT_ID: str = os.environ.get('REBOT_ID', '')
TOKEN_FILE: str = os.environ.get('TOKEN_FILE', 'tokens.json')
CHANNEL_TOKEN_FILE: str = os.environ.get('CHANNEL_TOKEN_FILE', 'channels_tokens.json')

# paths
COMMAND_DIR: str = os.environ.get('COMMAND_DIR', './commands/')
scripts_path: str = 'local_events/scripts/'


# QUEUES
LOCAL_EVENTS = 'local_events'
BEER_STAT = 'bs_donats'
DONATIONS_ALERTS = 'donations_alerts'
TWITCH_OUT = 'twitch_out'
TWITCH_EVENTS = 'retwitch_mssgs'
