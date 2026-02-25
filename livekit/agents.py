class Agent:
    """Minimal stub of livekit.agents.Agent used for tests.

    This stub accepts arbitrary kwargs in its constructor and exposes a
    `session` attribute that raises RuntimeError when accessed to mimic the
    live environment where session is only available when connected.
    """

    def __init__(self, **kwargs):
        # store provided components so tests can inspect if needed
        self._components = kwargs

    @property
    def session(self):
        raise RuntimeError("Agent session is not available in tests")
