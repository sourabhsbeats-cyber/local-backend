from django.utils.deprecation import MiddlewareMixin
from django.shortcuts import redirect

class NoCacheMiddleware(MiddlewareMixin):
    def process_response(self, request, response):
        # Prevent caching of any authenticated page
        response['Cache-Control'] = 'no-store, no-cache, must-revalidate, private'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'
        return response


class SecurityHeadersMiddleware(MiddlewareMixin):
    def process_response(self, request, response):
        response['Cache-Control'] = 'no-store, no-cache, must-revalidate, private'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'
        response['X-Frame-Options'] = 'DENY'
        response['X-Content-Type-Options'] = 'nosniff'
        response['Referrer-Policy'] = 'same-origin'
        return response