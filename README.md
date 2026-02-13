# Translation Daemon for macOS

A background service that monitors a directory for new files and processes them (e.g., for translation). It features persistence and startup scanning to ensure no files are missed.

## Features

- **Background Service**: Runs as a macOS Launch Agent.
- **Persistence**: Tracks processed files in a state file to avoid redundant processing.
- **Startup Scanning**: Automatically processes files added while the daemon was offline.
- **Configurable**: Managed via a YAML configuration file in `~/.config`.

## Installation

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd translation-daemon
   ```

2. **Install dependencies**:
   ```bash
   pip3 install -r requirements.txt
   ```

3. **Setup Configuration**:
   Create the configuration directory and copy the template:
   ```bash
   mkdir -p ~/.config/translation-daemon
   cp config/config.yaml ~/.config/translation-daemon/config.yaml
   ```
   Edit `~/.config/translation-daemon/config.yaml` to set your `watch_directory` and other preferences.

4. **Install the Launch Agent**:
   Update the paths in `com.translation.daemon.plist` to match your system, then:
   ```bash
   cp com.translation.daemon.plist ~/Library/LaunchAgents/
   launchctl load ~/Library/LaunchAgents/com.translation.daemon.plist
   ```

## Testing

To run the unit tests:
```bash
python -m pytest tests/
```

## Usage

Once installed, the daemon runs silently in the background. You can monitor its activity by checking the log file specified in your config (default: `/tmp/translation-daemon.log`).

To watch the logs in real-time:
```bash
tail -f /tmp/translation-daemon.log
```

To view the last 50 lines of the log:
```bash
tail -n 50 /tmp/translation-daemon.log
```

To stop the daemon:
```bash
launchctl unload ~/Library/LaunchAgents/com.translation.daemon.plist
```

To restart after a config change:
```bash
launchctl unload ~/Library/LaunchAgents/com.translation.daemon.plist
launchctl load ~/Library/LaunchAgents/com.translation.daemon.plist
```

## Configuration Options

- `watch_directory`: The full path to the directory you want to monitor.
- `output_directory`: Optional path to save translated files. If omitted, files are saved in the watch directory.
- `log_file`: Path where the daemon will write its logs.
- `state_file`: Path where the daemon will store its processed files list.
- `target_language`: The language code for translations.
- `project_id`: Your Google Cloud project ID.
- `location`: Google Cloud region (default: us-central1).
