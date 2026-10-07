# LiveKit Cloud builds this with `lk agent deploy`; it runs anywhere else too.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# LiveKit Cloud runs agents as a non-root user.
RUN useradd --create-home --uid 10001 agent && install -d -o agent /app
WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY --chown=agent . .
USER agent

# Model files of the installed plugins.
RUN python -m livekit.agents download-files

CMD ["python", "-m", "livekit.agents", "start", "agent.py"]
