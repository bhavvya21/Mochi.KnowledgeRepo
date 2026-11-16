FROM ollama/ollama:0.13.0
COPY deploy/ollama-start.sh /usr/local/bin/mochi-ollama
RUN chmod +x /usr/local/bin/mochi-ollama
ENTRYPOINT ["/usr/local/bin/mochi-ollama"]
