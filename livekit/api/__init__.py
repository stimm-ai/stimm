class AccessToken:
    def __init__(self, api_key, api_secret):
        pass

    def with_grants(self, grants):
        return self

    def to_jwt(self):
        return "a.b.c"


class VideoGrants:
    def __init__(self, **kwargs):
        pass
