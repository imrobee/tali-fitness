FROM node:24-slim

WORKDIR /app

# Install dependencies first so Docker caches this layer until package files change.
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY . .

EXPOSE 5173
CMD ["npm", "run", "dev"]
