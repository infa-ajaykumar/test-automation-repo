# Stage 1: Build the React app
FROM node:18-alpine AS build
WORKDIR /app
COPY package.json yarn.lock ./
# Using yarn, switch to npm if you used package-lock.json
RUN yarn install --frozen-lockfile
COPY . .
# Allow REACT_APP_API_BASE_URL to be set at build time
ARG REACT_APP_API_BASE_URL=/api # Default if not provided, or make it more specific like http://localhost:8000/api
ENV REACT_APP_API_BASE_URL=$REACT_APP_API_BASE_URL
RUN yarn build

# Stage 2: Serve the static files with Nginx
FROM nginx:1.25-alpine
COPY --from=build /app/build /usr/share/nginx/html

# Add a custom Nginx configuration to handle client-side routing
# and to allow API_BASE_URL to be configured at runtime via Nginx vars (more advanced)
# For simplicity now, we'll rely on a relative API_BASE_URL or one baked in at build time.
# A common approach for SPA routing:
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
