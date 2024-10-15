import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from src.config import *
from src.main import main
from src.utils.file_utils import get_file_extension, is_file_transferred
from src.models.folder import Folder

class Watcher:
    def __init__(self):
        self.observers = []
        self.lock = threading.Lock()

    def run(self):
        event_handler = Handler(self.lock)
        for folder in download_folders:
            observer = Observer()
            self.observers.append(observer)
            observer.schedule(event_handler, folder, recursive=True)
            observer.start()

        try:
            while True:
                time.sleep(sleep_timer)
        except Exception as e:
            print(f"ERROR in Watcher.run(): {e}")
            for observer in self.observers:
                observer.stop()
                print("Observer Stopped")
            for observer in self.observers:
                observer.join()
                print("Observer Joined")

class Handler(FileSystemEventHandler):
    def __init__(self, lock):
        self.lock = lock

    def on_created(self, event):
        with self.lock:
            start_time = time.time()
            global grouped_notifications

            try:
                global transferred_files, transferred_dirs

                extension = get_file_extension(event.src_path)
                base_name = os.path.basename(event.src_path)
                is_hidden = base_name.startswith(".")
                is_valid_file = os.path.isfile(event.src_path)
                in_file_extensions = extension in file_extensions

                if not event.event_type == "created":
                    return None

                if not is_valid_file or extension in image_extensions or is_hidden:
                    return None

                print(f"\n\tEvent Type: {event.event_type}")
                print(f"\tEvent Src Path: {event.src_path}")

                if not extension:
                    print("\t\t -No extension found, skipped.")
                    return None

                if event.is_directory:
                    print("\t\t -Is a directory, skipped.")
                    return None

                elif transferred_files and event.src_path in transferred_files:
                    print("\t\t -Already processed, skipped.")
                    return None

                elif not in_file_extensions:
                    if not delete_unacceptable_files_toggle:
                        print("\t\t -Not in file extensions and delete_unacceptable_files_toggle is not enabled, skipped.")
                        return None
                    elif (delete_unacceptable_files_toggle or convert_to_cbz_toggle) and (extension not in unacceptable_keywords and "\\" + extension not in unacceptable_keywords) and not (convert_to_cbz_toggle and extension in convertable_file_extensions):
                        print("\t\t -Not in file extensions, skipped.")
                        return None

                send_message("\nStarting Execution (WATCHDOG)", discord=False)

                embed = handle_fields(
                    DiscordEmbed(
                        title="Starting Execution (WATCHDOG)",
                        color=purple_color,
                    ),
                    [
                        {
                            "name": "File Found",
                            "value": f"```{event.src_path}```",
                            "inline": False,
                        }
                    ],
                )

                send_discord_message(
                    None,
                    [Embed(embed, None)],
                )

                print(f"\n\tFile Found: {event.src_path}\n")

                if not os.path.isfile(event.src_path):
                    return None

                files = [file for folder in download_folders for file in get_all_files_recursively_in_dir_watchdog(folder)]

                while True:
                    all_files_transferred = True
                    print(f"\nTotal files: {len(files)}")

                    for file in files:
                        print(f"\t[{files.index(file) + 1}/{len(files)}] {os.path.basename(file)}")

                        if file in transferred_files:
                            print("\t\t-already transferred")
                            continue

                        is_transferred = is_file_transferred(file)

                        if is_transferred:
                            print("\t\t-fully transferred")
                            transferred_files.append(file)
                            dir_path = os.path.dirname(file)
                            if dir_path not in download_folders + transferred_dirs:
                                transferred_dirs.append(os.path.dirname(file))
                        elif not os.path.isfile(file):
                            print("\t\t-file no longer exists")
                            all_files_transferred = False
                            files.remove(file)
                            break
                        else:
                            print("\t\t-still transferring...")
                            all_files_transferred = False
                            break

                    if all_files_transferred:
                        time.sleep(watchdog_discover_new_files_check_interval)

                        new_files = [file for folder in download_folders for file in get_all_files_recursively_in_dir_watchdog(folder)]

                        if files != new_files:
                            all_files_transferred = False
                            if len(new_files) > len(files):
                                print(f"\tNew transfers: +{len(new_files) - len(files)}")
                                files = new_files
                            elif len(new_files) < len(files):
                                break
                        elif files == new_files:
                            break

                    time.sleep(watchdog_discover_new_files_check_interval)

                print("\nAll files are transferred.")

                transferred_dirs = [create_folder_obj(x) if not isinstance(x, Folder) else x for x in transferred_dirs]

            except Exception as e:
                send_message(f"Error with watchdog on_any_event(): {e}", error=True)

            if profile_code == "main()":
                cProfile.run(profile_code, sort="cumtime")
            else:
                main()

            end_time = time.time()
            execution_time = end_time - start_time
            minutes, seconds = divmod(execution_time, 60)
            minutes, seconds = int(minutes), int(seconds)

            execution_time_message = f"{minutes} minute{'s' if minutes != 1 else ''}" if minutes else ""
            execution_time_message += f" and " if minutes and seconds else ""
            execution_time_message += f"{seconds} second{'s' if seconds != 1 else ''}" if seconds else ""
            execution_time_message = execution_time_message.strip() or "less than 1 second"

            send_message(f"\nFinished Execution (WATCHDOG)\n\tExecution Time: {execution_time_message}", discord=False)

            embed = handle_fields(
                DiscordEmbed(
                    title="Finished Execution (WATCHDOG)",
                    color=purple_color,
                ),
                [
                    {
                        "name": "Execution Time",
                        "value": f"```{execution_time_message}```",
                        "inline": False,
                    }
                ],
            )

            grouped_notifications = group_notification(grouped_notifications, Embed(embed, None))

            if grouped_notifications:
                sent_status = send_discord_message(None, grouped_notifications)
                if sent_status:
                    grouped_notifications = []

            send_message("\nWatching for changes... (WATCHDOG)", discord=False)

def create_folder_obj(root, dirs=None, files=None):
    return Folder(
        root,
        dirs if dirs is not None else [],
        os.path.basename(os.path.dirname(root)),
        os.path.basename(root),
        get_all_files_recursively_in_dir_watchdog(root) if files is None else files,
    )

def get_all_files_recursively_in_dir_watchdog(dir_path):
    results = []
    for root, dirs, files in os.walk(dir_path):
        files = [f for f in files if not f.startswith(".")]
        for file in files:
            file_path = os.path.join(root, file)
            if file_path not in results:
                extension = get_file_extension(file_path)
                if extension not in image_extensions:
                    results.append(file_path)
                elif not compress_image_option and (download_folders and dir_path in paths):
                    results.append(file_path)
    return results
