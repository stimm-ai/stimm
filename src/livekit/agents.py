class Agent:
    """Minimal stub of livekit.agents.Agent used for tests (src copy).

    Mirrors the repo-root stub so code importing from either path works
    during different PYTHONPATH configurations.
    """

    def __init__(self, **kwargs):
        self._components = kwargs

    @property
    def session(self):
        raise RuntimeError("Agent session is not available in tests")
