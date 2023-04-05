FROM node:14.21-slim
ENV NODE_ENV=production
WORKDIR /app
COPY . .
RUN yarn install --production=true
# EXPOSE 8090
CMD ["node", "index.js"]
