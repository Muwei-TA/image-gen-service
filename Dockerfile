FROM ubuntu:22.04

RUN apt-get update && \
    apt-get install -y python3 curl unzip && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /workspace/image-gen-service

# Ensure python output is unbuffered so we can see logs immediately
ENV PYTHONUNBUFFERED=1

CMD ["python3", "-m", "app.main"]
