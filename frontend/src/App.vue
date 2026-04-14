<template>
  <div id="booruhub-app">
    <AppNavbar />
    <main id="page-container">
      <router-view />
    </main>
    <ToastContainer />
  </div>
</template>

<script setup lang="ts">
import AppNavbar from './components/AppNavbar.vue'
import ToastContainer from './components/ToastContainer.vue'
</script>
