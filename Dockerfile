# Build stage
FROM python:3.9-slim-buster as builder
RUN apt-get update && apt-get install -y build-essential
RUN mkdir /komga-cover-extractor
WORKDIR /komga-cover-extractor
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt
COPY . .

# Production stage
FROM python:3.9-slim-buster
RUN mkdir /komga-cover-extractor
WORKDIR /komga-cover-extractor
COPY --from=builder /root/.local /root/.local
COPY --from=builder /komga-cover-extractor .
ENV PATH=/root/.local/bin:$PATH
CMD ["python3", "main.py"]

# Set image name and tag
LABEL maintainer="eggu"
LABEL version="1.0.0"
LABEL description="Komga Cover Extractor"
