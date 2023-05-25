# Use a specific version of the Python image
FROM python:3.11.0-alpine3.15

# Set the working directory to /app
WORKDIR /app

# Create a new user called "appuser"
RUN addgroup -g 1000 appuser && adduser -u 1000 -G appuser -D appuser

# Copy the current directory contents into the container at /app
COPY . .

# Install necessary packages and requirements
RUN apk add --no-cache unrar tzdata \
    && pip3 install --no-cache-dir -r requirements.txt \
    && rm -rf /var/cache/apk/*

# Switch to "appuser"
USER appuser

# Set the default CMD arguments for the script
CMD python3 -u komga_cover_extractor.py --paths="$PATHS" --download_folders="$DOWNLOAD_FOLDERS" --webhook="$WEBHOOK" --bookwalker_check="$BOOKWALKER_CHECK" --compress="$COMPRESS" --compress_quality="$COMPRESS_QUALITY" --bookwalker_webhook_urls="$BOOKWALKER_WEBHOOK_URLS" --watchdog="$WATCHDOG" --new_volume_webhook="$NEW_VOLUME_WEBHOOK"
