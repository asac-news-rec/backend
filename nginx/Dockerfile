# syntax=docker/dockerfile:1
FROM nginx:stable-alpine
COPY nginx/default.conf.template /etc/nginx/templates/default.conf.template
COPY web/ /usr/share/nginx/html/
