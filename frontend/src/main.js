import { createApp } from 'vue'
import { createPinia } from 'pinia'
import {
  FrappeUI,
  setConfig,
  frappeRequest,
} from 'frappe-ui'
import { spritePlugin, Icon } from 'frappe-ui/experimental'
import App from './App.vue'
import router from './router'
import './index.css'

const app = createApp(App)

// In frappe-ui v1, $socket is expected to be assigned by the host application if socket.io is used.
// Defining $socket prevents runtime exceptions when components or plugins inspect $socket.
app.config.globalProperties.$socket = null

setConfig('resourceFetcher', frappeRequest)

app.use(FrappeUI, { resources: true })
app.use(spritePlugin)
app.component('Icon', Icon)
app.use(router)
app.use(createPinia())

app.mount('#app')
