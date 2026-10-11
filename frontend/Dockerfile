FROM node:22-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm install --no-audit --no-fund
COPY . .
RUN npm run build
FROM node:22-alpine
WORKDIR /app
COPY --from=builder /app/build ./build
COPY --from=builder /app/package.json ./package.json
RUN npm install --omit=dev --no-audit --no-fund
EXPOSE 3003
ENV HOST=0.0.0.0 PORT=3003 NODE_ENV=production
CMD ["node","build"]
