FROM node:20-alpine

WORKDIR /app

# Install dependencies first for better layer caching
COPY package.json package-lock.json ./
RUN npm ci

# Copy project source
COPY . .

EXPOSE 5173

# --host is required so Vite is reachable from outside the container
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
