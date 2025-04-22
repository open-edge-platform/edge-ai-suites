<template>
  <div class="container">
    <div id="map"></div>
    <div id="text">
      <Screenshot />
    </div>
  </div>
</template>

<script lang="ts">
import { defineComponent } from 'vue';
import Screenshot from './Screenshot.vue';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

export default defineComponent({
  name: 'MapView',
  components: {
    Screenshot,
  },
  data() {
    return {
      map: null as L.Map | null,
    };
  },
  mounted() {
    this.initMap();
    window.addEventListener('resize', this.resizeMap);
  },
  beforeDestroy() {
    window.removeEventListener('resize', this.resizeMap);
  },
  methods: {
    initMap() {
      this.map = L.map('map').setView([33.4484, -112.0740], 25); // Phoenix coordinates

      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
      }).addTo(this.map);

      L.marker(
        [33.4484, -112.0740]
      ).addTo(this.map)
        .bindPopup('11 N Central Ave #4, Phoenix, AZ')
        .openPopup();

      this.resizeMap();
    },
    resizeMap() {
      if (this.map) {
        this.map.invalidateSize();
      }
    }
  }
});
</script>

<style>
@import 'leaflet/dist/leaflet.css';

html, body {
  height: 100%;
  margin: 0;
}

.container {
  display: flex;
  align-items: flex-start; /* Align items at the top */
  justify-content: flex-start; /* Optional: Align horizontally to the start */
  height: 100vh;
  width: 100vw;
}

#map {
  width: 65%;
  height: 100%;
}

#text {
  width: 35%;
  height: 100%;
  display: flex;
  flex-direction: column; /* Ensure the iframe is aligned vertically */
  align-items: flex-start; /* Align items to the top */
  justify-content: flex-start; /* Align items to the top */
}

#text p {
 
  text-align: center;
}
</style>