from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from authlib.integrations.flask_client import OAuth

limiter = Limiter(key_func=get_remote_address, default_limits=[])
oauth = OAuth()
