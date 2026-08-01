FROM node:20-alpine
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm install
COPY . .
ARG NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build && \
    cp -r .next/static .next/standalone/.next/static && \
    (test -d public && cp -r public .next/standalone/public || true)
EXPOSE 3000
ENV PORT=3000
CMD ["node", ".next/standalone/server.js"]
