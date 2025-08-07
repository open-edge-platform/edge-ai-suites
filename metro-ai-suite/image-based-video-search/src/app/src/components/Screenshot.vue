<template>
    <div ref="videoFrame" class="video-frame">
      <iframe
        ref="iframe"
        class="responsive-iframe"
        src="/stream/"
        title="Local Stream"
        frameborder="0"
        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
        allowfullscreen
      ></iframe>
    </div>
    <div class="btn-group" style="width: 100%">
      <button @click="startAnalysis" v-if="pipeline == null" :style="{ width: screenshot ? '20%' : '25%' }">Analyze Stream</button>
      <button @click="stopAnalysis" v-if="pipeline != null" :style="{ width: screenshot ? '20%' : '25%' }">Stop Analysis</button>
      <button @click="captureScreenshot" :style="{ width: screenshot ? '20%' : '25%' }">Capture Frame</button>
      <button @click="triggerFileUpload" :style="{ width: screenshot ? '20%' : '25%' }">Upload Image</button>
      <input type="file" ref="fileInput" @change="handleFileUpload" style="display: none;" accept="image/*" />
      <button v-if="screenshot" @click="cropImage" style="width: 20%" >Search Object</button>
      <button @click="clearDatabase" :style="{ 
        width: screenshot ? '20%' : '25%',
        backgroundColor: pipeline ? 'gray' : 'darkorange',
        border: pipeline ? '1px solid gray' : '1px solid #7f4600e0'
      }">Clear Database</button>
    </div>
    <div v-if="screenshot" class="screenshot-preview">      
          <vue-cropper
            ref="cropper"
            :src="screenshot"
            @change="onCropChange"
          />
    </div>
    <div v-if="imageData.length" class="image-list">
      <h4>Search Results:</h4>
      <div class="filters">
        <label for="from-date">From:</label>
        <input type="datetime-local" id="from-date" v-model="fromDatetime" />
        <label for="to-date">To:</label>
        <input type="datetime-local" id="to-date" v-model="toDatetime" />
        <label for="sort-by">Sort by:</label>
        <select id="sort-by" v-model="sortBy">
          <option value="date">Date</option>
          <option value="distance">Distance</option>
          <option value="label">Label</option>
        </select>
      </div>
      <ul>
        <li v-for="(data, index) in filteredImageData" :key="data.url + '-' + index">
          <img :src="data.url" :alt="data.url" />
          <div style="display: flex; flex-direction: column;">
            <span>Distance: {{ data.distance.toFixed(4) }}</span>
            <span>Label: {{ data.label }}</span>
            <span>Timestamp: {{ data.datetime }}</span>
          </div>
        </li>
      </ul>
    </div>
</template>

<script type="ts">
import { defineComponent } from 'vue';
import axios from "axios";
import html2canvas from "html2canvas";
import { Cropper } from "vue-advanced-cropper";
import "vue-advanced-cropper/dist/style.css";

export default defineComponent({
  name: 'Screenshot',
  components: {
    VueCropper: Cropper,
  },
  data() {
    return {
      screenshot: null, // To store the screenshot as a base64 image
      croppedImage: null, // To store the cropped image
      coordinates: null, // To store the cropper coordinates
      canvas: null, // To store the cropper canvas
      video: null, // To store the video element
      pipeline: null, // To store the pipeline id
      imageData: [], // To store the image data
      fromDatetime: '1970-01-01T00:00', // To store the initial datetime to filter
      toDatetime: new Date(Date.now() - new Date().getTimezoneOffset() * 60000).toISOString().slice(0, 16), // To store the final datetime to filter
      sortBy: 'date' // To store the sort by option
    };
  },
  computed: {
    filteredImageData() {
      return this.imageData
          .filter(data => {
            const date = new Date(data.timestamp / 1000000); // Use timestamp instead of datetime
            const from = this.fromDatetime ? new Date(this.fromDatetime) : null;
            const to = this.toDatetime ? new Date(this.toDatetime) : null;
            return (!from || date >= from) && (!to || date <= to);
          })
          .sort((a, b) => {
            if (this.sortBy === 'distance') {
              return b.distance - a.distance;
            } else if (this.sortBy === 'label') {
              return a.label.localeCompare(b.label);
            }
            
            return b.timestamp - a.timestamp;
          });
    }
  },
  methods: {
    async captureScreenshot() {
      if (!this.video) {
        console.log("Get video from iframe")
        const iframe = this.$refs.iframe;
        const iframeDocument = iframe.contentDocument || iframe.contentWindow.document;
        const video = iframeDocument.querySelector('video');

        if (video) {
          this.video = video;
        } else {
          console.error('Video element not found in iframe.');
        }
      }

      if (this.video) {
        try {
          const canvas = document.createElement('canvas');
          canvas.width = this.video.videoWidth;
          canvas.height = this.video.videoHeight;
          const context = canvas.getContext('2d');
          context.drawImage(this.video, 0, 0, canvas.width, canvas.height);
          this.screenshot = canvas.toDataURL('image/png');
          this.imageData = [];
        } catch (error) {
          console.error('Failed to capture screenshot of video frame:', error);
        }
      } else {
        console.error('Video element not found for screenshot capture.');
      }
    },
    triggerFileUpload() {
      this.imageData = [];
      this.screenshot = null;
      this.$refs.fileInput.click();
    },
    handleFileUpload(event) {
      const file = event.target.files[0];
      if (file) {
        const reader = new FileReader();
        reader.onload = (e) => {
          this.screenshot = e.target.result;
        };
        reader.readAsDataURL(file);
        this.$refs.fileInput.value = null; // Reset the file input value
      }
    },
    async startAnalysis() {
      const body = {
          source: {
              uri: "rtsp://ibvs-mediamtx:8554/stream",
              type: "uri"
          },
          destination: {
              frame: {
                  type: "rtsp",
                  path: "filter-pipeline"
              }
          }
      };

      fetch("/pipelines/user_defined_pipelines/filter-pipeline", {
          method: "POST",
          headers: {
              "Content-Type": "application/json"
          },
          body: JSON.stringify(body)
      })
      .then(response => response.json())
      .then(data => {
          console.log("Pipeline created successfully:", data);
          this.pipeline = data;
      })
      .catch(error => console.error('Error:', error))
    },
    async stopAnalysis() {
      if (this.pipeline) {
        fetch(`/pipelines/${this.pipeline}`, {
            method: "DELETE"
        })
        .then(response => response.json())
        .then(data => {
            console.log("Pipeline stopped successfully:", data);
            this.pipeline = null;
        })
        .catch(error => console.error('Error:', error))
      } else {
        console.error('No pipeline to stop.');
      }
    },
    async clearDatabase() {
      fetch("/clear/", {
          method: "POST"
      })
      .then(response => response.json())
      .then(data => console.log("Database reloaded successfully:", data))
      .catch(error => console.error('Error:', error))
    },
    onCropChange({ coordinates, canvas }) {
      this.coordinates = coordinates;
      this.canvas = canvas;
    },
    cropImage() {
      if (this.canvas) {
        this.croppedImage = this.canvas.toDataURL('image/png');
        this.sendCroppedImage();
      }
    },
    async sendCroppedImage() {
      if (this.croppedImage) {
        try {
          const blob = await fetch(this.croppedImage).then(res => res.blob());
          const formData = new FormData();
          formData.append('images', blob, 'cropped_image.png');

          const response = await axios.post('/search/', formData, {
            headers: {
              'Content-Type': 'multipart/form-data'
            }
          });

          console.log('Image sent successfully:', response.data[0]);

          // Reset cropped image
          this.screenshot = null;

          // Iterate over response.data and fetch images
          let results = await Promise.all(response.data[0].map(async (data) => {
            console.log("data", data);
            if (typeof data.entity.filename === 'string') {
              return {
                url: data.entity.filename,
                distance: data.distance,
                label: data.entity.label,
                timestamp: data.entity.timestamp,
                datetime: new Date(Number(data.entity.timestamp) / 1000000).toLocaleString()
              };
            } else {
              console.error('Filename is not a string:', data.entity.filename);
              return null;
            }
          }).filter(url => url !== null));

          this.imageData = results.sort((a, b) => {
            if (this.sortBy === 'distance') {
              return b.distance - a.distance;
            } else if (this.sortBy === 'label') {
              return a.label.localeCompare(b.label);
            }
            
            return b.timestamp - a.timestamp;
          });

        } catch (error) {
          console.error('Failed to send cropped image:', error);
        }
      } else {
        console.error('No cropped image to send.');
      }
    }
  },
});
</script>

<style>
body, html {
  margin: 0;
  padding: 0;
  height: 100%;
}

.video-frame {
  width: 100%; /* Set the width */
  height: 35%; /* Set the height */
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column; /* Ensure the iframe is aligned vertically */
  align-items: flex-start; /* Align items to the top */
  justify-content: flex-start; /* Align items to the top */
}

.responsive-iframe {
  width: 100%; /* Set the width */
  height: 100%; /* Set the height */
  border: none; /* Remove the border */
  display: block; /* Ensure the iframe is displayed as a block element */
}

.screenshot-preview {
  margin-top: 10px;
  width: 100%; /* Set the width */
  /* height: 157.5px; Set the height */
  /* margin-left:15%;   */
}

.image-list {
  width: 95%; /* Set a fixed width */
  height: 59%; /* Set a fixed height */
  overflow-y: auto; /* Enable vertical scrolling */
  padding: 10px; /* Add padding */
}

.image-list h4 {
  background-color: #663c1f; /* Set background color */
  margin: 0; /* Remove margin */
  color:white;
}

.image-list ul {
  list-style-type: none;
  padding: 0;
}

.image-list li {
  display: flex;
  align-items: center; /* Align items vertically */
  margin-bottom: 2px;
  width: 100%;
}

.image-list li img {
  width: 60%;
}

.image-list li > div {
  text-align: left;
  margin: 0px 0px 0px 20px;
}

.filters {
  margin-top: 8px;
  margin-bottom: -8px;
}

.filters input {
  margin-left: 5px;
}

.filters select {
  margin-left: 5px;
}

.filters label {
  margin-left: 10px;
}

.btn-group {
  height: 6%;
}

.btn-group button {
  background-color: #04AA6D; /* Green background */
  border: 1px solid green; /* Green border */
  color: white; /* White text */
  cursor: pointer; /* Pointer/hand icon */
  float: left; /* Float the buttons side by side */
  border-radius: 0; /* Make the button squared */
  height: 100%; /* Make the button take full height */
  font-size: calc(min(1.5vh, 1.5vw)); /* Responsive text size */
}

/* Clear floats (clearfix hack) */
.btn-group:after {
  content: "";
  clear: both;
  display: table;
}

.btn-group button:not(:last-child) {
  border-right: none; /* Prevent double borders */
}

/* Add a background color on hover */
.btn-group button:hover {
  background-color: #3e8e41;
}

</style>