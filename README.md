# Komga Cover Extractor

This application scans for and extracts covers from various file types, including manga and novel files. It also provides additional functionality such as file renaming, organizing, and integration with Bookwalker and Komga.

## Project Structure

```
komga-cover-extractor/
├── src/
│   ├── __init__.py
│   ├── config.py
│   ├── main.py
│   ├── extract_covers.py
│   ├── file_operations.py
│   ├── bookwalker.py
│   ├── komga.py
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── image_utils.py
│   │   ├── file_utils.py
│   │   └── string_utils.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── folder.py
│   │   ├── file.py
│   │   ├── volume.py
│   │   ├── path.py
│   │   └── bookwalker.py
│   └── handlers/
│       ├── __init__.py
│       └── watchdog_handler.py
├── settings.py
├── requirements.txt
└── README.md
```

## Installation

1. Clone the repository:
   ```
   git clone https://github.com/your-username/komga-cover-extractor.git
   cd komga-cover-extractor
   ```

2. Create a virtual environment and activate it:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
   ```

3. Install the required packages:
   ```
   pip install -r requirements.txt
   ```

4. Copy `settings.py.example` to `settings.py` and modify the settings according to your needs.

## Usage

To run the application, use the following command:

```
python -m src.main [arguments]
```

For a list of available arguments, run:

```
python -m src.main --help
```

## Features

- Extract covers from manga and novel files
- Rename and organize files
- Integration with Bookwalker for checking new releases
- Integration with Komga for library management
- Watchdog functionality for monitoring file changes

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
