FROM python:3.14.0a1-slim

ARG APP_VERSION
ENV APP_VERSION=$APP_VERSION

ENV SERVER_HOST=0.0.0.0
ENV SERVER_PORT=4000
ENV SERVER_WORKERS_COUNT=2

# setup working directory for container
WORKDIR /usr/src/app

# copy project to the image
COPY . .
# install dependencies
RUN pip install --no-cache-dir -r requirements.txt

CMD [ "/bin/bash", "bin/run" ]
