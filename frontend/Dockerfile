FROM node:20-alpine

WORKDIR /app

# Copy package config files
COPY package*.json ./

# Install dependencies
RUN npm install

# Copy all frontend source code
COPY . .

# Expose Vite dev server port
EXPOSE 5173

# Run Vite in dev mode and bind to all interfaces
CMD ["npm", "run", "dev", "--", "--host"]
