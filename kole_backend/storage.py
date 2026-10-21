import time
from django.contrib.staticfiles.storage import StaticFilesStorage

# Dynamic cache buster based on server start time
STATIC_VERSION = str(int(time.time()))

class CacheBustingStaticFilesStorage(StaticFilesStorage):
    """
    Subclass of StaticFilesStorage that appends a cache-busting query parameter
    to all static URLs in development. This bypasses Chrome / Edge disk cache
    which aggressively caches broken stylesheet MIME types from previous sessions.
    """
    def url(self, name):
        url = super().url(name)
        separator = '&' if '?' in url else '?'
        return f"{url}{separator}v={STATIC_VERSION}"
