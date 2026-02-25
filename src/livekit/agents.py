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

    async def update_instructions(self, instructions):
        pass


class WorkerOptions:
    def __init__(self, **kwargs):
        pass


class cli:
    @staticmethod
    def run_app(options):
        pass


class AgentSession:
    def __init__(self, **kwargs):
        pass

    async def start(self, **kwargs):
        pass

    def on(self, event_name):
        def decorator(f):
            return f

        return decorator

    async def interrupt(self):
        pass

    async def say(self, text):
        pass

    def generate_reply(self, **kwargs):
        pass


class JobContext:
    def __init__(self):
        self.room = None

    async def connect(self, **kwargs):
        pass


class RoomInputOptions:
    def __init__(self, **kwargs):
        pass
