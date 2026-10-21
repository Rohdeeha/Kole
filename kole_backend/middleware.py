from django.conf import settings

class DevNoCacheMiddleware:
    """
    Development middleware that forces browsers (especially Chrome/Edge)
    to always revalidate assets and never serve stale cached files with
    previous broken MIME types or unstyled content.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if settings.DEBUG:
            response['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
            response['Pragma'] = 'no-cache'
            response['Expires'] = '0'
        return response
