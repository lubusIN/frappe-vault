import { createApp } from 'vue'
import { createPinia } from 'pinia'
import {
  FrappeUI,
  setConfig,
  frappeRequest,
  resourcesPlugin,
  pageMetaPlugin,
} from 'frappe-ui'
import { spritePlugin } from 'frappe-ui/icons'
import App from './App.vue'
import router from './router'
import './index.css'

const app = createApp(App)

setConfig('resourceFetcher', frappeRequest)

app.use(FrappeUI, { socketio: false })
app.use(resourcesPlugin)
app.use(pageMetaPlugin)
app.use(spritePlugin)
app.use(router)
app.use(createPinia())

app.mount('#app')
