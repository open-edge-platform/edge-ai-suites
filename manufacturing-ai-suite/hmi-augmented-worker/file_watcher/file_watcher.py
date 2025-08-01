#
# Copyright (C) 2025 Intel Corporation.
#
# SPDX-License-Identifier: Apache-2.0
#

import os
import time
import logging
import requests
import signal
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# --- Logging Configuration ---
logging.basicConfig(
    format="%(asctime)s: %(name)s: %(levelname)s: %(message)s", level=logging.INFO
)

# List of file extensions or patterns to ignore
IGNORED_EXTENSIONS = ['.swp', '.swx', '.tmp']
IGNORED_SUFFIXES = ['~']
IGNORED_TEMP_FILENAMES = ['4913']  # 4913 is a common temporary file suffix for vim
DEBOUNCE_INTERVAL = 2.0 # seconds
DOCUMENT_ENDPOINT = os.getenv("DOCUMENT_ENDPOINT", "http://localhost:8888/documents")

# Global flag for shutdown
should_stop = False

def handle_shutdown(signum, func):
    global should_stop
    logging.info("Received shutdown signal.")
    should_stop = True

# Register signal handlers
signal.signal(signal.SIGINT, handle_shutdown)
signal.signal(signal.SIGTERM, handle_shutdown)

# --- File Event Handler ---
class FileChangeHandler(FileSystemEventHandler):
    def __init__(self, existing_files):
        super().__init__()
        self.last_modified = {}
        self.existing_files = existing_files

    def should_ignore(self, path):
        filename = os.path.basename(path)
        return (
            any(path.endswith(ext) for ext in IGNORED_EXTENSIONS) or
            any(path.endswith(suffix) for suffix in IGNORED_SUFFIXES) or
            filename in IGNORED_TEMP_FILENAMES
        )

    def send_file_to_api(self, file_path):
        try:
            with open(file_path, 'rb') as f:
                files = {'files': (os.path.basename(file_path), f)}
                response = requests.post(DOCUMENT_ENDPOINT, files=files)
                if response.status_code == 200:
                    logging.info(f"Successfully sent {file_path} for context creation.")
                else:
                    logging.warning(f"Failed to send {file_path}. Status code: {response.status_code}")

        except Exception as e:
            logging.error(f"Error sending {file_path} to API: {e}")

    def delete_file_to_api(self, file_path):
        delete_document_url = f"{DOCUMENT_ENDPOINT}?document={os.path.basename(file_path)}"

        try:
            response = requests.delete(delete_document_url)
            if response.status_code == 204:
                logging.info(f"Successfully deleted {file_path} from API.")
            else:
                logging.warning(f"Failed to delete {file_path}. Status code: {response.status_code}")

        except Exception as e:
            logging.error(f"Error deleting {file_path} from API: {e}")

    def on_any_event(self, event):
        if event.is_directory or self.should_ignore(event.src_path):
            return

        now = time.time()
        last_modified_time = self.last_modified.get(event.src_path, 0)

        if event.event_type == 'created':
            logging.info(f"File created: {event.src_path}")

        elif event.event_type == 'modified':
            if now - last_modified_time < DEBOUNCE_INTERVAL:
                return

            self.last_modified[event.src_path] = now

            logging.info(f"File modified: {event.src_path}")

            # add file into the list if it is not exist previously
            # else skip
            if event.src_path not in self.existing_files:
                self.existing_files.add(event.src_path)

            # check if the file is not empty, send for context creation
            # else return message and not sending for context creation
            if os.path.getsize(event.src_path) > 0:
                self.send_file_to_api(event.src_path)
            else:
                logging.info(f"File {event.src_path} is created without content.")

        elif event.event_type == 'deleted':
            self.delete_file_to_api(event.src_path)
            self.existing_files.discard(event.src_path)
            logging.info(f"File deleted: {event.src_path}")

# --- File Watcher class to encapsulate observer logic
class FileWatcher:
    def __init__(self, watch_directory):
        self.watch_directory = watch_directory
        self.existing_files = set()
        self.event_handler = FileChangeHandler(self.existing_files)
        self.observer = Observer()

    def list_existing_files(self):
        for root, _, files in os.walk(self.watch_directory):
            for file in files:
                file_path = os.path.join(root, file)
                if not self.event_handler.should_ignore(file_path):
                    self.existing_files.add(file_path)

    def start(self):
        logging.info(f"Starting to watch: {self.watch_directory}")

        # List existing files
        self.list_existing_files()
        logging.info(f"Initial existing files: {self.existing_files}")

        for file_path in self.existing_files:
            self.event_handler.send_file_to_api(file_path)

        self.observer.schedule(self.event_handler, self.watch_directory, recursive=True)
        self.observer.start()

        try:
            while not should_stop:
                time.sleep(1)

        finally:
            logging.info("Stopping observer...")
            self.observer.stop()
            self.observer.join()


# --- Entrypoint ---
if __name__ == "__main__":
    watch_path = os.getenv("WATCH_DIRECTORY", "/tmp/file")
    logging.info(f"Watching directory: {watch_path}")
    watcher = FileWatcher(watch_path)
    watcher.start()
