import os

# Render sets PORT automatically
bind = f"0.0.0.0:{os.environ.get('PORT', '10000')}"

workers     = 2        # Low RAM on free tier
timeout     = 300      # 5 min for large PDF imports
keepalive   = 5
preload_app = False    # CRITICAL: must be False — prevents DB thread-sharing error

accesslog   = "-"
errorlog    = "-"
loglevel    = "info"
