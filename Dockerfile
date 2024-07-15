# Use a specific version of the Python image
FROM python:3.11.4-slim-bookworm

# Set the working directory to /app
WORKDIR /app

# Create a new user called "appuser"
RUN useradd -m appuser

# Set the default environment variables
ARG PUID=1000
ARG PGID=1000

# Set the PYTHONUNBUFFERED environment variable to avoid partial output in logs
ENV PYTHONUNBUFFERED=1

# Add non-free to sources.list
RUN echo "deb http://deb.debian.org/debian bullseye non-free" >> /etc/apt/sources.list

# Set ownership to appuser and switch to "appuser"
RUN groupmod -o -g "$PGID" appuser && usermod -o -u "$PUID" appuser

# Allow users to specify UMASK (default value is 022)
ENV UMASK=022
RUN umask "$UMASK"

# Copy the current directory contents into the container at /app
COPY --chown=appuser:appuser . .

# Install necessary packages and requirements for the main script
RUN apt-get update
RUN apt-get install -y unrar tzdata nano
RUN pip3 install --no-cache-dir -r requirements.txt

# Install the requirements for the qbit_torrent_unchecker addon
RUN pip3 install --no-cache-dir -r /app/addons/qbit_torrent_unchecker/requirements.txt

# # Install the optional addon feature manga_isbn if true
ARG MANGA_ISBN
RUN if [ "$MANGA_ISBN" = "true" ]; then \
    apt-get update && \
    apt-get install -y wget && \
    apt-get install -y build-essential && \
    apt-get install -y xdg-utils xz-utils libopengl0 libegl1 libxcb-cursor0 && \
    wget -nv -O- https://download.calibre-ebook.com/linux-installer.sh | sh /dev/stdin && \
    apt-get install -y libicu-dev pkg-config python3-icu && \
    apt-get install -y /app/addons/manga_isbn/chrome/google-chrome-stable_current_amd64.deb && \
    apt-get install -y python3-pyqt5 && \
    apt-get -y install tesseract-ocr && \
    pip3 install --no-cache-dir -r /app/addons/manga_isbn/requirements.txt && \
    pip3 install /app/addons/manga_isbn/python-anilist-1.0.9/.; \
    fi

# # Install the optional addon feature epub_converter if true
ARG EPUB_CONVERTER
RUN if [ "$EPUB_CONVERTER" = "true" ]; then \
    apt-get install -y zip && \
    pip3 install --no-cache-dir -r /app/addons/epub_converter/requirements.txt; \
    fi

# Remove unnecessary packages and clean up
RUN apt-get autoremove -y
RUN rm -rf /var/lib/apt/lists/*

# Switch to "appuser"
USER appuser

# Run the addon script in the background and redirect the output to a log file, then run the main script in the foreground.
CMD python3 /app/addons/qbit_torrent_unchecker/qbit_torrent_unchecker.py --paths="$PATHS" --download_folders="$DOWNLOAD_FOLDERS" > /dev/null 2>&1 & python3 -u komga_cover_extractor.py --paths="$PATHS" --download_folders="$DOWNLOAD_FOLDERS" --webhook="$WEBHOOK" --bookwalker_check="$BOOKWALKER_CHECK" --compress="$COMPRESS" --compress_quality="$COMPRESS_QUALITY" --bookwalker_webhook_urls="$BOOKWALKER_WEBHOOK_URLS" --watchdog="$WATCHDOG" --watchdog_discover_new_files_check_interval="$WATCHDOG_DISCOVER_NEW_FILES_CHECK_INTERVAL" --watchdog_file_transferred_check_interval="$WATCHDOG_FILE_TRANSFERRED_CHECK_INTERVAL" --output_covers_as_webp="$OUTPUT_COVERS_AS_WEBP" --new_volume_webhook="$NEW_VOLUME_WEBHOOK"
