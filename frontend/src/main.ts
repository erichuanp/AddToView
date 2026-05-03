import { createApp } from 'vue'
import App from './App.vue'
import { router } from './router'
import './styles/glass.css'
// import once so the theme class is on <html> before first paint
import './composables/useTheme'

createApp(App).use(router).mount('#app')
