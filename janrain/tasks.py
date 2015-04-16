import requests

from django.contrib.auth.models import User

from celery import task
from celery.utils.log import get_task_logger

from janrain.exceptions import JanrainCaptureUpdateException
import janrain.utils


logger = get_task_logger(__name__)


@task(name='janrain.update_janrain_capture_user')
def update_janrain_capture_user(id, klass=User):
    user = klass.objects.get(id=id)
    try:
        janrain.utils.update_janrain_capture_user(user)
    except JanrainCaptureUpdateException, exc:
        # If rate limit is hit back off
        # todo: more elegant check
        if 'api_limit_error' in str(exc):
            raise update_janrain_capture_user.retry(exc=exc, countdown=3600)
        else:
            logger.error("Cannot update user %s, exc=%s" % (id, exc))
            raise update_janrain_capture_user.retry(exc=exc)
    except requests.exceptions.RequestException, exc:
        # This happens from time to time. Networks go down. No need to log.
        raise update_janrain_capture_user.retry(exc=exc)
