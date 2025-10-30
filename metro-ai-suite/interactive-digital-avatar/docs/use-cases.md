# Use Cases

## 2D Avatar

### 1. Prepare Avatar Character

To generate a 2d avatar character from a template video:

```bash
python prepare_2d_avatar.py -v input/video.mp4 -ai my-avatar
```

The terminal will show the completion progress, it may takes a few minutes.
![prepare_avatar_character](_images/prepare_avatar_character.png)

The avatar will be saved to the `output/avatars2d/my-avatar` directory.

If the client has multiple GPUs and you want the avatar to run on
a specific one, modify the `device` of the `ov` in the `/resource/config.yaml`.
For example, if your system detects an integrated GPU (GPU 0) and an
A770 (GPU 1), and you want to use the latter, change the variable from
`GPU` to `GPU.1`.

### 2. Generate Offline Video

#### 2.1 From keyboard input

To convert text to a video of a 2D avatar character, use the following command:

```bash
python text_to_2d_avatar.py -ai my-avatar
```

The terminal output will show information on the progress. When run for the
first time, it will display additional information about the downloaded content.

![generate_offline_video_keyboard_input](_images/generate_offline_video_keyboard_input.png)

Type a text in the console. The output video will be saved to the
`output/video` directory.

Type `exit` to exit the program.

#### 2.2 From input file

To convert a text file to a video of a 2D avatar character,
run the following command:

```bash
python file_to_2d_avatar.py -ai my-avatar -i input/text.txt
```

The terminal output will show information on the progress. When run for the
first time, it will display additional information about the downloaded content.

![generate_offline_video_input_file](_images/generate_offline_video_input_file.png)

The content from the input text file will be converted to a video of a 2D avatar
line by line. The output video will be saved to the `output/video` directory.

### 3.Display Online Video

In this part, the process will send messages to RAG to get answers, so make sure
that the [RAG](./get-started.md#prepare-rag) is ready. Additionally, you need
to provide a corresponding `base_url`in `/resource/config.yaml`.

#### 3.1 Text Chat with Avatar

Chat with a 2D avatar character via keyboard input.

```bash
python avatar2d_chat_online_text.py -ai my-avatar
```

The terminal output will show information on the progress, including the
keyboard input and the answer from RAG.

![display_online_video_text_chat_with_avatar](_images/display_online_video_text_chat_with_avatar.png)

Meanwhile, the avatar character will be displayed on the screen.

Type `exit` to exit the program.

#### 3.2 Voice Chat with Avatar

Start a voice chat with a 2D avatar character.

```bash
python avatar2d_chat_online_voice.py -ai my-avatar
```

The terminal will show information on the progress, including the output of ASR
(voice input) and the answer from RAG.

![display_online_video_voice_chat_with_avatar](_images/display_online_video_voice_chat_with_avatar.png)

Meanwhile, the avatar character will be displayed on the screen.

There are two ways to chat with avatar character:

- Press and hold the `L` key on the keyboard and speak the question. Release it
  after you finish.
- Speak the wake words defined in `da/config/wake/wake_words.py`.
  Ask the questions after `Wake by word` has been displayed in the console log.

Press `Ctrl+c` to exit the program.

## 3D Avatar

Start the render to show the 3D avatar character.

### 1. Run socket server

```bash
python -m da.avatar3d.socketio_server
```

### 2. Start avatar

In this part, the process will send messages to RAG and SAiD, so make sure that
[RAG](./get-started.md#prepare-rag) and
[SAiD](./get-started.md#prepare-project-code-and-models-on-server) are ready.
Additionally, you need to provide a corresponding `base_url`in
`/resource/config.yaml`.

Open a new terminal for the following operations.
If the avatar starts correctly, the terminal of socker server will show
a similar information:

![socket_server_log](_images/socket_server_log.png)

The terminal will show information on the progress,
including the keyboard/ASR input and the answer from RAG.

#### 2.1 Text Chat with Avatar

Start a text chat with a 3D avatar character.

```bash
python avatar3d_chat_online_text.py
```

Input `exit` to exit program.

#### 3.2 Voice Chat with Avatar

Start a voice chat with a 3D avatar character.

```bash
python avatar3d_chat_online_voice.py
```
