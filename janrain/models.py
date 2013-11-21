import logging
import requests

from django.db import models
from django.contrib.auth.models import User
from django.contrib.auth import user_logged_in
from django.dispatch import receiver
from django.db.models.signals import post_save
from django.utils import simplejson
from django.conf import settings

from janrain.exceptions import JanrainCaptureUpdateException
from janrain.utils import user_to_janrain_capture_dict, update_janrain_capture_user, \
    CAPTURE_URL, BASE_CAPTURE_DATA
import janrain.tasks


logger = logging.getLogger(__name__)


class JanrainUser(models.Model):
    """Model for both Janrain Engage and Janrain Capture data"""
    user       = models.ForeignKey(User, unique=True, related_name='janrain_user')
    username   = models.CharField(max_length=512, blank=True, null=True)
    provider   = models.CharField(max_length=64, blank=True, null=True)
    identifier = models.URLField(max_length=512, blank=True, null=True)
    avatar     = models.URLField(max_length=512, blank=True, null=True)
    url        = models.URLField(max_length=512, blank=True, null=True)
    uuid       = models.CharField(max_length=128, blank=True, null=True)


@receiver(user_logged_in)
def on_user_logged_in(sender, **kwargs):
    """Upon login create and/or update the Janrain user if it does not exist.
    The logged in handler is a good place for this since we don't want a bulk
    upload to trigger many calls to Janrain. This call must be blocking."""

    # Do nothing if url not set
    if not CAPTURE_URL:
        return

    user = kwargs['user']

    # Users added by Engage also need to end up in Capture. These users have a
    # JainrainUser object with an empty uuid value initially. Normal users
    # have no JanrainUser object at all initially.
    janrain_user = None
    uuid = None
    qs = user.janrain_user.all()
    if qs.exists():
        janrain_user = qs[0]
        uuid = janrain_user.uuid

    if not uuid:
        data = BASE_CAPTURE_DATA.copy()
        data['attributes'] = simplejson.dumps(user_to_janrain_capture_dict(user))
        # See http://developers.janrain.com/documentation/api-methods/capture/entity/create-2/
        try:
            response = requests.post(
                '%s/entity.create' % CAPTURE_URL, data=data, timeout=5
            )
        except requests.exceptions.RequestException:
            # Failure is not a problem since the Janrain profile will be
            # created on a future login
            pass
        else:
            result = simplejson.loads(response.content)
            if result['stat'] == 'ok':
                if not janrain_user:
                    janrain_user = JanrainUser.objects.create(user=user, uuid=result['uuid'])
                else:
                    janrain_user.uuid = result['uuid']
                    janrain_user.save()
            else:
                logger.error("Cannot create user %s, stat=%s" % (user.id, result['stat']))


@receiver(post_save)
def on_user_saved(sender, **kwargs):
    """Update values on Janrain"""

    # No redundant call to Janrain on newly created user
    if kwargs['created']:
        return

    # Allow User and subclasses of User
    if not issubclass(sender, User):
        return

    user = kwargs['instance']
    strategy = getattr(settings, 'JANRAIN', {}).get('capture_update_strategy', 'synchronous')
    if strategy == 'synchronous':
        try:
            update_janrain_capture_user(user)
        except (requests.exceptions.RequestException, JanrainCaptureUpdateException), exc:
            logger.error("Cannot update user %s, exc=%s" % (user.id, exc))
    elif strategy == 'celery':
        janrain.tasks.update_janrain_capture_user.delay(user.id, klass=user.__class__)
