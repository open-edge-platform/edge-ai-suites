Sync
Method: POST
URL: http://127.0.0.1:8000/api/tasks/video-summary
Body Type: raw (选择 JSON)
```json
{
    "video_url": "C:/videos/classroom_test.mp4"
}
```
Async
Method: POST
URL: http://127.0.0.1:8000/api/tasks/video-summary
Body Type: raw (选择 JSON)
```json
{
    "video_url": "C:/videos/videos/classroom_test.mp4",
    "sync": false,
    "callback_url": "https://webhook.site/28865adb-376c-4a0a-ac59-5204a60f9fe3"
}
```
http://127.0.0.1:8000/tasks/video-upload
xxx