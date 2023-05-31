# Use a specific version of the Python image
FROM python:3.11.0-slim-buster

# Set the working directory to /app
WORKDIR /app

# Create a new user called "appuser"
RUN useradd -m appuser
ARG PUID=1000
ARG PGID=1000

# Set ownership to appuser and switch to "appuser"
RUN echo "deb http://deb.debian.org/debian buster non-free" >> /etc/apt/sources.list
RUN apt-get update
RUN groupmod -o -g "$PGID" appuser && usermod -o -u "$PUID" appuser
RUN chown -R appuser:appuser /app
RUN chmod -R a+w /app

# Copy the current directory contents into the container at /app
COPY . .

# Install necessary packages and requirements
RUN apt-get install -y unrar tzdata
RUN pip3 install --no-cache-dir -r requirements.txt
RUN apt-get autoremove -y
RUN rm -rf /var/lib/apt/lists/*

# Switch to "appuser"
USER appuser

# Set the default CMD arguments for the script
CMD python3 -u komga_cover_extractor.py --paths="$PATHS" --download_folders="$DOWNLOAD_FOLDERS" --webhook="$WEBHOOK" --bookwalker_check="$BOOKWALKER_CHECK" --compress="$COMPRESS" --compress_quality="$COMPRESS_QUALITY" --bookwalker_webhook_urls="$BOOKWALKER_WEBHOOK_URLS" --watchdog="$WATCHDOG" --new_volume_webhook="$NEW_VOLUME_WEBHOOK"