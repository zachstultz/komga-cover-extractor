# Use a specific version of the Python image
FROM python:3.11.4-slim-bookworm as build

# Install necessary build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl \
    && rm -rf /var/lib/apt/lists/*

ENV VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

ADD https://astral.sh/uv/install.sh /install.sh
RUN chmod 755 /install.sh && /install.sh && rm /install.sh

COPY . /app
WORKDIR /app

RUN /root/.cargo/bin/uv venv /opt/venv && \
    /root/.cargo/bin/uv pip install --no-cache --compile -r requirements.txt && \
    /root/.cargo/bin/uv pip install --no-cache --compile -r addons/qbit_torrent_unchecker/requirements.txt

FROM python:3.11.4-slim-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
    unrar-free tzdata nano rclone \
    && rm -rf /var/lib/apt/lists/*

COPY --from=build /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY --chown=appuser:appuser . /app
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

# Install the optional addon feature manga_isbn if true
ARG MANGA_ISBN
RUN if [ "$MANGA_ISBN" = "true" ]; then \
    apt-get update && \
    apt-get install -y --no-install-recommends \
    wget build-essential xdg-utils xz-utils libopengl0 libegl1 libxcb-cursor0 \
    libicu-dev pkg-config python3-icu python3-pyqt5 tesseract-ocr \
    && wget -nv -O- https://download.calibre-ebook.com/linux-installer.sh | sh /dev/stdin \
    && apt-get install -y /app/addons/manga_isbn/chrome/google-chrome-stable_current_amd64.deb \
    && /opt/venv/bin/pip install --no-cache-dir -r /app/addons/manga_isbn/requirements.txt \
    && /opt/venv/bin/pip install /app/addons/manga_isbn/python-anilist-1.0.9/. \
    && apt-get purge -y --auto-remove wget \
    && rm -rf /var/lib/apt/lists/*; \
    fi

# Install the optional addon feature epub_converter if true
ARG EPUB_CONVERTER
RUN if [ "$EPUB_CONVERTER" = "true" ]; then \
    apt-get update && \
    apt-get install -y --no-install-recommends zip \
    && /opt/venv/bin/pip install --no-cache-dir -r /app/addons/epub_converter/requirements.txt \
    && apt-get purge -y --auto-remove \
    && rm -rf /var/lib/apt/lists/*; \
    fi

# Switch to "appuser"
USER appuser

# Set the entrypoint to run the addon script in the background and the main script in the foreground
CMD python /app/addons/qbit_torrent_unchecker/qbit_torrent_unchecker.py --paths="$PATHS" --download_folders="$DOWNLOAD_FOLDERS" > /dev/null 2>&1 & python -u komga_cover_extractor.py --paths="$PATHS" --download_folders="$DOWNLOAD_FOLDERS" --webhook="$WEBHOOK" --bookwalker_check="$BOOKWALKER_CHECK" --compress="$COMPRESS" --compress_quality="$COMPRESS_QUALITY" --bookwalker_webhook_urls="$BOOKWALKER_WEBHOOK_URLS" --watchdog="$WATCHDOG" --watchdog_discover_new_files_check_interval="$WATCHDOG_DISCOVER_NEW_FILES_CHECK_INTERVAL" --watchdog_file_transferred_check_interval="$WATCHDOG_FILE_TRANSFERRED_CHECK_INTERVAL" --new_volume_webhook="$NEW_VOLUME_WEBHOOK"
