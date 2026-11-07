# сборка
FROM node:24-alpine AS build

WORKDIR /app

RUN npm install -g pnpm@11

COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

COPY . .
RUN pnpm build

# раздача
FROM nginx:alpine

# шаблон конфига: официальный entrypoint подставит BACKEND_URL через envsubst
COPY nginx.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html

ENV BACKEND_URL=http://backend:8000

EXPOSE 80
