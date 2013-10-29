import requests

from django.db import models
from django.contrib.auth.models import User
from django.contrib.auth import user_logged_in
from django.dispatch import receiver
from django.db.models.signals import post_save
from django.utils import simplejson
from django.conf import settings

from janrain.utils import user_to_janrain_dict


CAPTURE_URL = getattr(settings, 'JANRAIN', {}).get('capture_url', None)
BASE_DATA = {
    'client_id': getattr(settings, 'JANRAIN', {}).get('capture_client_id', None),
    'client_secret': getattr(settings, 'JANRAIN', {}).get('capture_client_secret', None),
    'type_name': 'user'
}


class JanrainUser(models.Model):
    """Model for both Janrain Engage and Janrain Capture data"""
    user       = models.ForeignKey(User, unique=True, related_name='janrain_user')
    username   = models.CharField(max_length=512, blank=True, null=True),
    provider   = models.CharField(max_length=64, blank=True, null=True)
    identifier = models.URLField(max_length=512, blank=True, null=True)
    avatar     = models.URLField(max_length=512, blank=True, null=True)
    url        = models.URLField(max_length=512, blank=True, null=True)
    uuid       = models.CharField(max_length=128, blank=True, null=True)


@receiver(user_logged_in)
def on_user_logged_in(sender, **kwargs):
    """Upon login create and/or update the Janrain user if it does not exist.
    The logged in handler is a good place for this since we don't want a bulk
    upload to trigger many calls to Janrain."""

    # Do nothing if url not set
    if not CAPTURE_URL:
        return

    user = kwargs['user']
    #import pdb;pdb.set_trace()
    print "ON USER LOGGED IN"

    if not user.janrain_user.exists():
        data = BASE_DATA.copy()
        data['attributes'] = simplejson.dumps(user_to_janrain_dict(user))
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
                janrain_user = JanrainUser.objects.create(user=user, uuid=result['uuid'])


@receiver(post_save)
def on_user_saved(sender, **kwargs):
    """Update values on Janrain"""

    # No redundant call to Janrain on newly created user
    if kwargs['created']:
        return

    # Allow User and subclasses of User
    if not issubclass(sender, User):
        return

    print "ON USER SAVED"
    user = kwargs['instance']

    #import pdb;pdb.set_trace()
    if user.janrain_user.exists():
        # A OneToOneField would have been nice :)
        janrain_user = user.janrain_user.all()[0]
        if janrain_user.uuid:
            data = BASE_DATA.copy()
            data['uuid'] = janrain_user.uuid
            data['value'] = simplejson.dumps(user_to_janrain_dict(user))
            # We want exceptions to propagate
            response = requests.post(
                '%s/entity.update' % CAPTURE_URL, data=data, timeout=5
            )
            result = simplejson.loads(response.content)
            #if result['stat'] == 'ok':
            #
