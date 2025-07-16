# How to Build from Source

This document provides step-by-step instructions for building the `ChatQnA Core` sample application and File Watcher service from source. Refer to the [prerequisites section](./get-started.md/#prerequisites) in the guide to install the appropriate software dependencies.

## Build ChatQnA Core from Source

For detailed instructions on building from source, visit the [Build from Source Guide](https://github.com/open-edge-platform/edge-ai-libraries/blob/main/sample-applications/chat-question-and-answer-core/docs/user-guide/build-from-source.md).

### ChatQnA Core Docker Compose Deployment

For docker compose deployment instructions, visit the [Running Application Container Guide](https://github.com/open-edge-platform/edge-ai-libraries/blob/main/sample-applications/chat-question-and-answer-core/docs/user-guide/build-from-source.md#running-the-application-container).


## Build File Watcher Service from Source

In the Windows® environment, the File Watcher Service works with the HMI application to continuously monitor file system activities such as creation, modification, and deletion. When it detects any changes, it sends the relevant file data over the network to the `ChatQnA Core` service for ingestion and contextual processing, supporting Retrieval-Augmented Generation (RAG) workflows.

### Prerequisites

- **Python Installer**: Visit the [official Python website](https://www.python.org/downloads/windows/). Select the latest version available under the "Python Releases for Windows" section.

- **Git[OPTIONAL]**: Visit the [official GIT website](https://git-scm.com/download/win) to download the executable

### Build File Watcher Service in Windows

To build the File Watcher executable binary, follow these steps:

1. Clone and download the source code by either using Git clone or downloading the source code as a ZIP file directly from the [repository](https://github.com/open-edge-platform/edge-ai-suites).
   ```bash
   git clone https://github.com/open-edge-platform/edge-ai-suites.git edge-ai-suites
   ```

2. Set up the Virtual Environment with Python venv.

   - Open Command Prompt.

        - Press `Win + R`, type `cmd`, and hit Enter.

   - Create Virtual Environment.

     ```sh
     # Replace `<venv_name>` with your preferred name.
     python -m venv <venv_name>
     ```

3. Activate the Virtual Environment.

   ```sh
   <venv_name>\Scripts\activate
   ```

   Once it's activated, the environment name appears in parentheses as follows:

   ```
   (venv_name) C:\Users\YourName\project>
   ```

4. Navigate to the Project folder downloaded in Step 1.

   ```sh
   cd edge-ai-suites\manufacturing-ai-suite\hmi-augmented-worker\file_watcher
   ```

5. Install Packages Inside the Virtual Environment.

   ```sh
   pip install -r requirements.txt --no-cache-dir
   ```

   If your system is behind a proxy, do as follows:

   ```sh
   # Replace <your_proxy> and <port> to your network proxy and port number
   pip install -r requirements.txt --no-cache-dir --proxy <your_proxy>:<port>
   ```
   On Windows®, typically, proxy information can be fetched using the command,
   ```sh
   netsh winhttp show proxy
   ```
   This will output one of the following two outputs:
   ```sh
   Current WinHTTP proxy settings:
        Direct access (no proxy server).
   ```
   or
   ```sh
   Current WinHTTP proxy settings:
        Proxy Server:  <your_proxy>:<port>
        Bypass List:   <bypass_list>
   ```

6. Set up Environment Variables using `.bat`.

   - Open and edit the values for the variables with your corresponding setup.
   - Then, execute the `.bat` file as shown:

     ```sh
     .\set_env_vars.bat
     ```

7. Compile and build the File Watcher Service executable.

   ```sh
   pyinstaller file_watcher.py -F --onefile
   ```

8. Execute the File Watcher Service executable.

   - Before starting the File Watcher Service, ensure that your backend `ChatQnA Core` service is up.

     ```sh
     .\dist\file_watcher.exe
     ```

9. After the service starts, the file watcher continuously monitors file events occurring in the designated folder specified by `WATCH_DIRECTORY` in the `set_env_vars.bat` file, until it is stopped by a keyboard interrupt.

## Troubleshooting

### `Error: [WinError 206] The filename or extension is too long`

#### Description:

When attempting to install packages using `pip` on Windows, you may encounter the following error:

```sh
ERROR: Could not install packages due to an OSError: [WinError 206] The filename or extension is too long: "...
```

#### Solution:

- Modify the registry entry using Registry Editor.

  1. Open Registry Editor:

     - Press `Win + R` to open the Run dialog.
     - Type `regedit` and press Enter.

  2. Navigate to the FileSystem Key:

     - Go to: `HKEY_LOCAL_MACHINE\SYSTEM\CurrentControlSet\Control\FileSystem`

  3. Modify LongPathsEnabled:

     - Find the `LongPathsEnabled` entry.
     - Double-click on it and set its value to `1`.
     - Click OK to save the changes.

After enabling long path support, you may need to restart your computer for the changes to take effect. Once done, try running your `pip install` command again.

If the issue persists, consider using a shorter path for your project or virtual environment, as mentioned earlier. Moving your project to a directory with a shorter path can help avoid hitting the path length limit.
