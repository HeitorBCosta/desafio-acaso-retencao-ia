# Etapa 1: compila o React com as versões travadas no package-lock.json.
FROM node:26-alpine AS build
WORKDIR /web
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

# Etapa 2: serve os arquivos estáticos e repassa /api para o contêiner da API.
FROM nginx:alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /web/dist /usr/share/nginx/html
EXPOSE 80
