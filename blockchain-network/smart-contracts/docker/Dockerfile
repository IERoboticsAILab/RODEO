FROM node:20-alpine

WORKDIR /app

# Install dependencies first (for better caching)
COPY package*.json ./
RUN npm install

# Copy the rest of the smart contract files
COPY . .

# Clean any previous builds
RUN npm run clean || true

# Default command: compile and deploy
CMD ["sh", "-c", "npm run compile && npm run deploy:ganache"]
