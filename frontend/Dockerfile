# Dev server Vite (React) — use com docker-compose e volume para hot reload
FROM node:20-alpine

WORKDIR /app

RUN apk add --no-cache libc6-compat

COPY package.json package-lock.json* ./
RUN npm ci

COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

COPY . .

ENV VITE_API_URL=/api
ENV VITE_PROXY_TARGET=http://backend:8000

EXPOSE 5173

ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]
