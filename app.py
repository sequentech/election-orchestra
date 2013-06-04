import logging
from flask import Flask

from api import app as api_app

logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)

### configuration

# debug, set to false on production deployment
DEBUG = True

# database configuration
SQLALCHEMY_DATABASE_URI = 'sqlite:////db.sqlite'

# import custom settings if any
try:
    from custom_settings import *
except:
    pass

# boostrap our little application
app.config.from_object(__name__)
app.register_blueprint(api_app, url_prefix='/api/v1')


if __name__ == "__main__":
    app.run(threaded=True)
