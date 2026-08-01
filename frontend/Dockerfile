FROM node:20-alpine AS base
WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm ci

COPY . .

EXPOSE 3000
ENV NEXT_PUBLIC_API_URL=""
CMD ["npm", "run", "dev"]
