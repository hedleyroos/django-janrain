import requests

from django.utils import simplejson
from django.conf import settings

from janrain.exceptions import JanrainCaptureUpdateException


CAPTURE_URL = getattr(settings, 'JANRAIN', {}).get('capture_url', None)
BASE_CAPTURE_DATA = {
    'client_id': getattr(settings, 'JANRAIN', {}).get('capture_client_id', None),
    'client_secret': getattr(settings, 'JANRAIN', {}).get('capture_client_secret', None),
    'type_name': 'user'
}


def user_to_janrain_capture_dict(user):
    """Translate user fields into corresponding Janrain fields"""

    field_map = getattr(settings, 'JANRAIN', {}).get('field_map', None)
    if not field_map:
        field_map = {
            'first_name': {'name': 'givenName'},
            'last_name': {'name': 'familyName'},
            'email': {'name': 'email'},
            'username': {'name': 'displayName'},
        }

    result = {}
    for field in user._meta.fields:
        if field.name in field_map:
            fm = field_map[field.name]
            value = getattr(user, field.name)
            func = fm.get('function', None)
            if func:
                value = func(value)
            result[fm['name']] = value

    return result


def update_janrain_capture_user(user):
    if user.janrain_user.exists():
        janrain_user = user.janrain_user.all()[0]
    else:
        return

    if janrain_user.uuid:
        data = BASE_CAPTURE_DATA.copy()
        data['uuid'] = janrain_user.uuid
        data['value'] = simplejson.dumps(user_to_janrain_capture_dict(user))
        response = requests.post(
            '%s/entity.update' % CAPTURE_URL, data=data, timeout=10
        )
        result = simplejson.loads(response.content)
        if result['stat'] != 'ok':
            raise JanrainCaptureUpdateException("Return stat %s" % result['stat'])
