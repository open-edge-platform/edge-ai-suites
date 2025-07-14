# How to Build from Source

This document provides step-by-step instructions for building the ChatQ&A Core microservices and File Watcher service from source. Please refer to the prerequiresites section in the guide to install the appropriate software dependencies.

## Build ChatQ&A Core from Source

For detailed instructions on building from source, please visit the [Build from Source Guide](https://github.com/open-edge-platform/edge-ai-libraries/blob/main/sample-applications/chat-question-and-answer-core/docs/user-guide/build-from-source.md)

### ChatQ&A Core Docker Compose Deployment

For docker compose deployment instructions, please visit the [Running Application Container Guide](https://github.com/open-edge-platform/edge-ai-libraries/blob/main/sample-applications/chat-question-and-answer-core/docs/user-guide/build-from-source.md#running-the-application-container)


## Build File Watcher Service from Source

In the `Windows environment`, the File Watcher Service operates in conjunction with the HMI application, continuously monitoring file system activities such as creation, modification, and deletion. Upon detecting any changes, it transmits the relevant file data over the network to the ChatQ&A service for ingestion and contextual processing, thereby supporting Retrieval-Augmented Generation (RAG) workflows.

### Prerequisites

- **Python Installer**: Visit the [official Python website](https://www.python.org/downloads/windows/). Select the latest version available under the "Python Releases for Windows" section.

- **Git[OPTIONAL]**: Visit the [official GIT website](https://git-scm.com/download/win) to download the executable

### Build File Watcher Service in Windows

To build the File Watcher executable binary, follow these steps:

1. Clone and download the source code by either using Git clone or downloading the source code as a ZIP file directly from the [repository](https://github.com/open-edge-platform/edge-ai-suites).

2. Setup the Virtual Environment with python venv.

   - Open Command Prompt.

        - Press `Win + R`, type `cmd`, and hit Enter.

   - Create Virtual Environment.

     ```sh
     # Replace `<venv_name>` with your preffered name.
     python -m venv <venv_name>
     ```

3. Activate the Virtual Environment.

   ```sh
   <venv_name>\Scripts\activate
   ```

   Once it's activated, you will see the environment name in parenthesis as below:

   ```
   (venv_name) C:\Users\YourName\project>
   ```

4. Navigate to Project Folder downloaded in Step 1.

   ```sh
   cd \path\to\your\project\manufacturing-ai-suite\hmi-augmented-worker\file_watcher
   ```

5. Install Packages Inside the Virtual Environment.

   ```sh
   pip install -r requirements.txt --no-cache-dir
   ```

   If your system is behind a proxy, please try below:

   ```sh
   # Replace <your_proxy> and <port> to your network proxy and port number
   pip install -r requirements.txt --no-cache-dir --proxy <your_proxy>:<port>
   ```

6. Setup Environment Variables using `.bat`.

   - Open and edit the values for the variables with your corresponding setup.

   - Then, execute the `.bat` file via below:

     ```sh
     .\set_env_vars.bat
     ```

7. Compile and Build the File Watcher Service executable.

   ```sh
   pyinstaller file_watcher.py -F --onefile
   ```

8. Execute the File Watcher Service executable.

   - Before starting the File Watcher Service, please do make sure that your backend ChatQ&A Core service is up.

     ```sh
     .\dist\file_watcher.exe
     ```

9. After the service starts, the file watcher will continuously monitor file events occurring in the designated folder specified by `WATCH_DIRECTORY` in the `set_env_vars.bat` file, until it is stopped by a keyboard interrupt.

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

After enabling long path support, you might need to restart your computer for the changes to take effect. Once done, try running your `pip install` command again.

If the issue persists, consider using a shorter path for your project or virtual environment as mentioned earlier. Moving your project to a directory with a shorter path can help avoid hitting the path length limit.