FROM node:22-alpine AS build
WORKDIR /app
COPY package.json ./package.json
RUN npm install --no-audit --no-fund
COPY . .
ARG VITE_API_BASE_URL=http://localhost:8000
ARG VITE_AUTH_MODE=demo
ARG VITE_COGNITO_DOMAIN=
ARG VITE_COGNITO_CLIENT_ID=
ARG VITE_COGNITO_REDIRECT_URI=http://localhost:8080/app
ARG VITE_COGNITO_LOGOUT_URI=http://localhost:8080/
ARG VITE_POSE_MODEL_URL=https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task
ARG VITE_POSE_WASM_URL=https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.22/wasm
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL VITE_AUTH_MODE=$VITE_AUTH_MODE VITE_COGNITO_DOMAIN=$VITE_COGNITO_DOMAIN VITE_COGNITO_CLIENT_ID=$VITE_COGNITO_CLIENT_ID VITE_COGNITO_REDIRECT_URI=$VITE_COGNITO_REDIRECT_URI VITE_COGNITO_LOGOUT_URI=$VITE_COGNITO_LOGOUT_URI VITE_POSE_MODEL_URL=$VITE_POSE_MODEL_URL VITE_POSE_WASM_URL=$VITE_POSE_WASM_URL
RUN npm run build

FROM nginx:1.27-alpine AS runtime
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 8080
CMD ["nginx", "-g", "daemon off;"]
