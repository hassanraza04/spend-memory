FROM node:24-alpine

WORKDIR /app

RUN corepack enable

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY apps/web/package.json ./apps/web/package.json
RUN pnpm install --frozen-lockfile

COPY apps/web ./apps/web

ENV SPEND_MEMORY_API_URL=http://api:8000
RUN pnpm --dir apps/web build

EXPOSE 3000

CMD ["pnpm", "--dir", "apps/web", "start", "--hostname", "0.0.0.0"]
