FROM node:18-alpine

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm install

# Copy source
COPY . .

# Build
ARG REACT_APP_API_BASE
ENV REACT_APP_API_BASE=$REACT_APP_API_BASE
RUN npm run build

# Serve with lightweight static server
RUN npm install -g serve
EXPOSE 3000
CMD ["sh", "-c", "serve -s build -p ${PORT:-3000}"]
