
FROM node:22-alpine AS monaco
WORKDIR /tmp/m
RUN npm pack monaco-editor@0.52.2 --silent && tar -xzf monaco-editor-*.tgz

FROM nginx:1.27-alpine
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=monaco /tmp/m/package/min/vs /usr/share/nginx/html/vendor/monaco/vs
COPY frontend/index.html frontend/styles.css frontend/app.js frontend/monaco-langs.js frontend/resources.js /usr/share/nginx/html/
COPY frontend/assets /usr/share/nginx/html/assets
COPY docs /usr/share/nginx/html/docs
