FROM python:3.12-slim
ARG DJANGO_SETTINGS_MODULE
ARG DJANGO_ADMIN_URL
ARG DJANGO_SECRET_KEY
ARG DATABASE_URL
ENV PYTHONUNBUFFERED=1 DJANGO_SETTINGS_MODULE=${DJANGO_SETTINGS_MODULE} DJANGO_ADMIN_URL=${DJANGO_ADMIN_URL} DJANGO_SECRET_KEY=${DJANGO_SECRET_KEY} DATABASE_URL=${DATABASE_URL} POETRY_VIRTUALENVS_CREATE=false

# Add new user to run the whole thing as non-root
RUN groupadd app
RUN adduser --ingroup app --home /app --disabled-password --gecos "" app

RUN apt-get update \
  && apt-get install -y --no-install-recommends curl \
  && rm -rf /var/lib/apt/lists/*

# Install build dependencies
RUN apt update \
	&& apt install -y gettext


# Set the correct timezone
RUN cp /usr/share/zoneinfo/Europe/Berlin /etc/localtime \
    && echo "Europe/Berlin" > /etc/timezone

# Copy Pipfile and install python dependencies
RUN curl -sSL https://install.python-poetry.org | POETRY_VERSION=2.3.2 python - \
  && ln -s /root/.local/bin/poetry /usr/local/bin/poetry
COPY --chown=app:app pyproject.toml poetry.lock /

RUN poetry install --no-interaction --no-ansi

# Copy dokku specific files to the project root
COPY --chown=app:app docker/dokku/* /app/
COPY --chown=app:app docker/dokku/entrypoint.sh /
RUN chmod +x entrypoint.sh /app/deploy.sh

USER app
WORKDIR /app

# Copy all related app files
COPY --chown=app:app . /app

ENTRYPOINT ["/entrypoint.sh"]
