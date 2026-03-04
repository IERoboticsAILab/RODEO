FROM node:20-bookworm-slim

# Pin Ganache for reproducibility
RUN npm install --global ganache@7.9.2

# Directory for persisted chain state
RUN mkdir -p /data
VOLUME ["/data"]

# Expose RPC port
EXPOSE 8545
EXPOSE 8546

ENTRYPOINT ["ganache"]
CMD ["--host","0.0.0.0", "--port","8545", "--server.ws","true","--db","/data", "--chain.chainId","1337", "--wallet.mnemonic","test test test test test test test test test test test junk", "--wallet.totalAccounts","20"]
