"""
CLI module for Komga Cover Extractor using Typer and Rich.
"""
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from typing_extensions import Annotated

app = typer.Typer(
    name="komga-cover-extractor",
    help="Scans for and extracts covers from zip, cbz, cbr, epub, and other archive files.",
    add_completion=False,
)
console = Console()


@dataclass
class CLIConfig:
    """Configuration object returned by CLI parsing."""
    paths: List[str]
    download_folders: List[str]
    webhook: List[str]
    bookwalker_check: bool
    compress: bool
    compress_quality: int
    bookwalker_webhook_urls: List[str]
    watchdog: bool
    new_volume_webhook: Optional[str]
    log_to_file: bool
    watchdog_discover_new_files_check_interval: int
    watchdog_file_transferred_check_interval: int
    output_covers_as_webp: bool


@app.command()
def extract_covers(
    paths: Annotated[
        Optional[List[str]],
        typer.Option(
            "-p",
            "--paths",
            help="The path/paths to be scanned for cover extraction.",
        ),
    ] = None,
    download_folders: Annotated[
        Optional[List[str]],
        typer.Option(
            "-df",
            "--download-folders",
            help="Download folder/folders for processing, renaming, and moving downloaded files.",
        ),
    ] = None,
    webhook: Annotated[
        Optional[List[str]],
        typer.Option(
            "-wh",
            "--webhook",
            help="Discord webhook URL for notifications about changes and errors.",
        ),
    ] = None,
    bookwalker_check: Annotated[
        bool,
        typer.Option(
            "-bwc",
            "--bookwalker-check",
            help="Check for new releases on BookWalker.",
        ),
    ] = False,
    compress: Annotated[
        bool,
        typer.Option(
            "-c",
            "--compress",
            help="Compress the extracted cover images.",
        ),
    ] = False,
    compress_quality: Annotated[
        int,
        typer.Option(
            "-cq",
            "--compress-quality",
            help="Quality of the compressed cover images (1-100).",
            min=1,
            max=100,
        ),
    ] = 40,
    bookwalker_webhook_urls: Annotated[
        Optional[List[str]],
        typer.Option(
            "-bwk-whs",
            "--bookwalker-webhook-urls",
            help="Webhook URLs for the BookWalker check.",
        ),
    ] = None,
    watchdog: Annotated[
        bool,
        typer.Option(
            "-wd",
            "--watchdog",
            help="Use watchdog library to watch for file changes in download folders.",
        ),
    ] = False,
    new_volume_webhook: Annotated[
        Optional[str],
        typer.Option(
            "-nw",
            "--new-volume-webhook",
            help="Discord webhook for new volume release notifications.",
        ),
    ] = None,
    log_to_file: Annotated[
        bool,
        typer.Option(
            "-ltf",
            "--log-to-file",
            help="Log changes and errors to a file.",
        ),
    ] = False,
    watchdog_discover_new_files_check_interval: Annotated[
        int,
        typer.Option(
            "--watchdog-discover-new-files-check-interval",
            help="Seconds to sleep before checking if all files are fully transferred.",
            min=1,
        ),
    ] = 30,
    watchdog_file_transferred_check_interval: Annotated[
        int,
        typer.Option(
            "--watchdog-file-transferred-check-interval",
            help="Seconds to sleep between file size checks when determining if a file is fully transferred.",
            min=1,
        ),
    ] = 5,
    output_covers_as_webp: Annotated[
        bool,
        typer.Option(
            "--output-covers-as-webp",
            help="Output covers as WebP format instead of JPG format.",
        ),
    ] = False,
):
    """
    Extract covers from manga/novel files.
    
    Scans specified paths for supported archive files and extracts their cover images.
    """
    # Validate that at least paths or download_folders are provided
    if not paths and not download_folders:
        console.print(
            "[red]Error:[/red] No paths or download folders were passed to the script.",
            style="bold",
        )
        console.print("Please provide at least one path (-p) or download folder (-df).")
        raise typer.Exit(1)
    
    # Display configuration
    _display_config(
        paths=paths,
        download_folders=download_folders,
        webhook=webhook,
        bookwalker_check=bookwalker_check,
        compress=compress,
        compress_quality=compress_quality,
        bookwalker_webhook_urls=bookwalker_webhook_urls,
        watchdog=watchdog,
        new_volume_webhook=new_volume_webhook,
        log_to_file=log_to_file,
        watchdog_discover_new_files_check_interval=watchdog_discover_new_files_check_interval,
        watchdog_file_transferred_check_interval=watchdog_file_transferred_check_interval,
        output_covers_as_webp=output_covers_as_webp,
    )
    
    # Return configuration for use by main script
    return CLIConfig(
        paths=paths or [],
        download_folders=download_folders or [],
        webhook=webhook or [],
        bookwalker_check=bookwalker_check,
        compress=compress,
        compress_quality=compress_quality,
        bookwalker_webhook_urls=bookwalker_webhook_urls or [],
        watchdog=watchdog,
        new_volume_webhook=new_volume_webhook,
        log_to_file=log_to_file,
        watchdog_discover_new_files_check_interval=watchdog_discover_new_files_check_interval,
        watchdog_file_transferred_check_interval=watchdog_file_transferred_check_interval,
        output_covers_as_webp=output_covers_as_webp,
    )


def _display_config(**kwargs):
    """Display the current configuration in a nice table."""
    console.print()
    console.print("[bold blue]Run Settings:[/bold blue]")
    console.print()
    
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Setting", style="cyan", width=40)
    table.add_column("Value", style="green")
    
    for key, value in kwargs.items():
        # Format the key nicely
        display_key = key.replace("_", " ").title()
        
        # Format the value
        if isinstance(value, list):
            if value:
                display_value = "\n".join(str(v) for v in value)
            else:
                display_value = "[dim]None[/dim]"
        elif isinstance(value, bool):
            display_value = "✓" if value else "✗"
        elif value is None:
            display_value = "[dim]None[/dim]"
        else:
            display_value = str(value)
        
        table.add_row(display_key, display_value)
    
    console.print(table)
    console.print()


def parse_args() -> CLIConfig:
    """
    Parse command line arguments and return configuration.
    
    This is the main entry point for integrating with the existing script.
    """
    import sys
    
    # Store the result here
    config_result = []
    
    # Temporarily replace extract_covers to capture its return value
    original_extract = app.registered_commands[0].callback
    
    def wrapper(*args, **kwargs):
        result = original_extract(*args, **kwargs)
        config_result.append(result)
        return result
    
    # Replace temporarily
    app.registered_commands[0].callback = wrapper
    
    try:
        # Run the app - it will call wrapper which captures the result
        app()
    except SystemExit as e:
        # Typer exits after running successfully
        if e.code == 0 and config_result:
            return config_result[0]
        raise
    finally:
        # Restore original callback
        app.registered_commands[0].callback = original_extract
    
    # If we got here, return the config
    if config_result:
        return config_result[0]
    raise RuntimeError("Failed to parse CLI arguments")


def main():
    """Entry point for the CLI when run standalone."""
    app()


if __name__ == "__main__":
    main()
