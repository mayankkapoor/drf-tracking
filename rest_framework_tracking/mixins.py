from .models import APIRequestLog
from django.db import transaction
from django.utils.timezone import now

from rest_framework import exceptions


class LoggingMixin(object):
    """Mixin to log requests"""
    def initial(self, request, *args, **kwargs):
        """Set current time on request"""
        # regular initialize
        super(LoggingMixin, self).initial(request, *args, **kwargs)

        # get user
        try:
            if request.user.is_authenticated():
                user = request.user
            else:  # AnonymousUser
                user = None
        except exceptions.AuthenticationFailed:
            # AuthenticationFailed exceptions are raised by django-rest-framework in case Token is invalid/expired
            user = None

        # get data dict
        try:
            data_dict = request.data.dict()
        except AttributeError:  # if already a dict, can't dictify
            data_dict = request.data

        # save to log
        request.log = APIRequestLog.objects.create(
            user=user,
            requested_at=now(),
            path=request.path,
            remote_addr=request.META['REMOTE_ADDR'],
            host=request.get_host(),
            method=request.method,
            query_params=request.query_params.dict(),
            data=data_dict,
        )

    def dispatch(self, *args, **kwargs):
        # Wrap normal processing in a transaction, so that even if
        # there's an IntegrityError somewhere along the way, we can still
        # log the response.
        # http://stackoverflow.com/questions/21458387/transactionmanagementerror-you-cant-execute-queries-until-the-end-of-the-atom
        with transaction.atomic():
            response = super(LoggingMixin, self).dispatch(*args, **kwargs)

        if hasattr(self, 'log'):
            # compute response time
            response_timedelta = now() - self.log.requested_at
            response_ms = int(response_timedelta.total_seconds() * 1000)

            # save to log
            self.log.response = response.rendered_content
            self.log.status_code = response.status_code
            self.log.response_ms = response_ms
            self.log.save()

        # return
        return response
