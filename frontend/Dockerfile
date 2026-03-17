# ── Build stage ──────────────────────────────────────────────
FROM node:20-alpine AS dev
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .

# ── Production build ────────────────────────────────────────
FROM dev AS build
RUN npm run build

# ── Serve with Nginx ────────────────────────────────────────
FROM nginx:alpine AS production
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
