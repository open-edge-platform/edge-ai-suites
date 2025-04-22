<template>
  <MapView />
</template>

<script lang="ts">
import { defineComponent } from 'vue';
import MapView from "./components/MapView.vue";

export default defineComponent({
  name: "AppContainer",
  components: {
    MapView,
  },
});
</script>

<style>
html,
body,
#app {
  height: 100%;
  margin: 0;
  padding: 0;
}
</style>

