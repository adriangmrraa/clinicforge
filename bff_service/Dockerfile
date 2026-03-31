FROM node:22-alpine

WORKDIR /app

COPY package*.json ./
RUN npm install

RUN addgroup -S appgroup && adduser -S appuser -G appgroup

COPY --chown=appuser:appgroup . .

RUN npm run build

USER appuser

EXPOSE 3000

CMD ["node", "dist/index.js"]
