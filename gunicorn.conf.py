# Gunicorn configuration for Render.com deployment
import multiprocessing

# Use gevent for async workers — prevents PDF import from killing other requests
worker_class = "gevent"
workers      = 2                   # Keep low on free tier (512MB RAM)
worker_connections = 100
timeout      = 300                 # 5 minutes — enough for large PDFs
keepalive    = 5
preload_app  = True                # Share memory across workers

# Logging
accesslog    = "-"
errorlog     = "-"
loglevel     = "info"

# Bind
bind         = "0.0.0.0:10000"
