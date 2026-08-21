FROM node:20-bullseye

# Install Python 3 et pip
RUN apt-get update && \
   apt-get install -y python3 python3-pip && \
   apt-get clean && \
   rm -rf /var/lib/apt/lists/*

# Install n8n globalement
RUN npm install -g n8n

# Dossier n8n (l'utilisateur node existe deja dans l'image de base)
RUN mkdir -p /home/node/.n8n && \
   chown -R node:node /home/node

USER node
WORKDIR /home/node

EXPOSE 5678

CMD ["n8n", "start"]