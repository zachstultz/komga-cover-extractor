# Use a specific version of the Python image
FROM python:3.11.0-slim-bullseye

# Set the working directory to /app
WORKDIR /app

# Create a new user called "appuser"
RUN useradd -m appuser
ARG PUID=1000
ARG PGID=1000

# Set ownership to appuser and switch to "appuser"
RUN echo "deb http://deb.debian.org/debian bullseye non-free" >> /etc/apt/sources.list
RUN apt-get update
RUN groupmod -o -g "$PGID" appuser && usermod -o -u "$PUID" appuser
RUN chown -R appuser:appuser /app

# Allow users to specify UMASK (default value is 022)
ENV UMASK 022
RUN umask "$UMASK"

# Copy the current directory contents into the container at /app
COPY . .

# Install necessary packages and requirements
RUN apt-get install -y unrar tzdata nano
RUN pip3 install --no-cache-dir -r requirements.txt

# Install the optional addon feature manga_isbn if true
ARG MANGA_ISBN
RUN if [ "$MANGA_ISBN" = "true" ]; then \
    apt-get install -y build-essential && \
    apt-get install -y wget && \
    apt-get install -y xdg-utils xz-utils libopengl0 libegl1 && \
    wget -nv -O- https://download.calibre-ebook.com/linux-installer.sh | sh /dev/stdin && \
    apt-get install -y libicu-dev pkg-config python3-icu && \
    wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb && \
    apt-get install -y ./google-chrome-stable_current_amd64.deb && \
    rm google-chrome-stable_current_amd64.deb && \
    apt-get install -y python3-pyqt5 && \
    apt-get -y install tesseract-ocr && \
    pip3 install --no-cache-dir -r /app/addons/manga_isbn/requirements.txt && \
    pip3 install /app/addons/manga_isbn/python-anilist-1.0.9/.; \
    fi

# Install the optional addon feature epub_converter if true
ARG EPUB_CONVERTER
RUN if [ "$EPUB_CONVERTER" = "true" ]; then \
    apt-get install -y zip && \
    pip3 install --no-cache-dir -r /app/addons/epub_converter/requirements.txt; \
    fi

RUN apt-get autoremove -y
RUN rm -rf /var/lib/apt/lists/*

# Switch to "appuser"
USER appuser

# Set the default CMD arguments for the script
CMD python3 -u komga_cover_extractor.py --paths="$PATHS" --download_folders="$DOWNLOAD_FOLDERS" --webhook="$WEBHOOK" --bookwalker_check="$BOOKWALKER_CHECK" --compress="$COMPRESS" --compress_quality="$COMPRESS_QUALITY" --bookwalker_webhook_urls="$BOOKWALKER_WEBHOOK_URLS" --watchdog="$WATCHDOG" --new_volume_webhook="$NEW_VOLUME_WEBHOOK"
