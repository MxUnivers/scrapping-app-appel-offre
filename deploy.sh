#!/bin/bash

APP_DIR="/opt/apps/scrapp-infosoluces"

rm -rf $APP_DIR/*
unzip /opt/upload/app.zip -d $APP_DIR

cd $APP_DIR

docker stop mon-app || true
docker rm mon-app || true

docker build -t mon-app-python .
docker run -d --name mon-app -p 8000:8000 mon-app-python