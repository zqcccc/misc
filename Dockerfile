FROM node:alpine3.17
ENV NODE_ENV=production
WORKDIR /app
COPY . .
RUN yarn install --production=true
# EXPOSE 8090
CMD ["node", "index.js"]
