<template>
  <div id="booruhub-app">
    <AppBackground />
    <AppNavbar />
    <main id="page-container">
      <router-view />
    </main>
    <ToastContainer />
  </div>
</template>

<script setup lang="ts">
import AppNavbar from './components/AppNavbar.vue'
import AppBackground from './components/AppBackground.vue'
import ToastContainer from './components/ToastContainer.vue'
</script>
