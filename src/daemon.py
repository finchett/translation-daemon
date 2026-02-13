import argparse
import datetime
import json
import logging
import sys
import time
from pathlib import Path

import yaml
from google.cloud import translate_v3 as translate
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer


class TranslationHandler(FileSystemEventHandler):
    def __init__(self, daemon):
        self.daemon = daemon

    def on_created(self, event):
        if not event.is_directory:
            self.daemon.process_file(Path(event.src_path))


class TranslationDaemon:
    def __init__(self, config_path):
        self.config_path = Path(config_path).expanduser().resolve()
        self.config = self.load_config()

        self.watch_dir = Path(self.config["watch_directory"]).expanduser().resolve()
        self.log_file = (
            Path(self.config.get("log_file", "/tmp/translation-daemon.log"))
            .expanduser()
            .resolve()
        )
        self.state_file = (
            Path(
                self.config.get("state_file", "~/.config/translation-daemon/state.json")
            )
            .expanduser()
            .resolve()
        )

        self.project_id = self.config.get("project_id")
        self.location = self.config.get("location", "us-central1")
        self.target_lang = self.config.get("target_language", "en")

        self.output_dir = None
        if self.config.get("output_directory"):
            self.output_dir = (
                Path(self.config["output_directory"]).expanduser().resolve()
            )
            self.output_dir.mkdir(parents=True, exist_ok=True)

        self.processed_files = self.load_state()
        self.setup_logging()

        self.client = None
        if not self.project_id:
            logging.error("project_id not found in config. Google Translate will fail.")
        else:
            try:
                self.client = translate.TranslationServiceClient(
                    client_options={"quota_project_id": self.project_id}
                )
                self.parent = f"projects/{self.project_id}/locations/{self.location}"
            except Exception as e:
                logging.error(f"Failed to initialize TranslationServiceClient: {e}")

    def load_config(self):
        if not self.config_path.exists():
            print(f"Error: Config file {self.config_path} does not exist.")
            sys.exit(1)
        with open(self.config_path, "r") as f:
            return yaml.safe_load(f)

    def load_state(self):
        if self.state_file.exists():
            try:
                with open(self.state_file, "r") as f:
                    return set(json.load(f))
            except Exception as e:
                print(f"Error loading state: {e}")
        return set()

    def save_state(self):
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.state_file, "w") as f:
            json.dump(list(self.processed_files), f)

    def setup_logging(self):
        logging.basicConfig(
            filename=self.log_file,
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    def process_file(self, file_path):
        file_path = Path(file_path).resolve()
        str_path = str(file_path)

        # Skip if already processed, is a directory, or is hidden
        if (
            str_path in self.processed_files
            or not file_path.is_file()
            or file_path.name.startswith(".")
        ):
            return

        # We only support PDFs for this specific Google Translate implementation
        if file_path.suffix.lower() != ".pdf":
            logging.info(
                f"Skipping {file_path.name}: only PDF translation is implemented."
            )
            return

        if not self.client:
            logging.error(
                f"Cannot translate {file_path.name}: Google Translate client not initialized. Check your project_id."
            )
            return

        current_time = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        new_name = f"{current_time}{file_path.suffix}"
        new_path = file_path.with_name(new_name)
        file_path.rename(new_path)
        file_path = new_path
        str_path = str(file_path)

        logging.info(f"Translating {file_path.name} to {self.target_lang}...")

        try:
            # Ensure file exists and is readable
            if not file_path.exists():
                return

            with open(file_path, "rb") as f:
                pdf_content = f.read()

            document_input_config = translate.DocumentInputConfig(
                content=pdf_content, mime_type="application/pdf"
            )

            request = translate.TranslateDocumentRequest(
                parent=self.parent,
                target_language_code=self.target_lang,
                document_input_config=document_input_config,
            )

            response = self.client.translate_document(request=request)
            translated_bytes = response.document_translation.byte_stream_outputs[0]

            if self.output_dir:
                out_path = self.output_dir / f"{file_path.stem}{file_path.suffix}"
            else:
                out_path = file_path.with_name(f"{file_path.stem}{file_path.suffix}")

            with open(out_path, "wb") as f:
                f.write(translated_bytes)

            self.processed_files.add(str_path)
            self.save_state()
            logging.info(f"Success! Saved as: {out_path}")

        except Exception as e:
            logging.error(f"Failed to translate {file_path.name}: {e}")

    def scan_existing_files(self):
        logging.info(f"Scanning {self.watch_dir} for existing files...")
        for item in self.watch_dir.iterdir():
            self.process_file(item)

    def run(self):
        if not self.watch_dir.exists():
            logging.error(f"Watch directory {self.watch_dir} does not exist.")
            sys.exit(1)

        logging.info(f"Starting translation-daemon on {self.watch_dir}")
        self.scan_existing_files()

        event_handler = TranslationHandler(self)
        observer = Observer()
        observer.schedule(event_handler, str(self.watch_dir), recursive=False)
        observer.start()

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            observer.stop()
        observer.join()


def main():
    parser = argparse.ArgumentParser(description="Translation Daemon for macOS")
    parser.add_argument(
        "--config",
        type=str,
        default="~/.config/translation-daemon/config.yaml",
        help="Path to the config file",
    )

    args = parser.parse_args()
    daemon = TranslationDaemon(args.config)
    daemon.run()


if __name__ == "__main__":
    main()
