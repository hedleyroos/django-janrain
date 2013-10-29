from django.conf import settings


def user_to_janrain_dict(user):
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
    for fieldname in user._meta.fields:
        if fieldname in field_map:
            fm = field_map[k]
            value = getattr(user, fieldname)
            func = fm.get('function', None)
            if func:
                value = func(value)
            result[fm['name']] = value

    return result
