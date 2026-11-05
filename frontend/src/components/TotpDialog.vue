<template>
  <Dialog
    v-model="modelValue"
    title="TOTP Code (2FA)"
    size="sm"
    @update:modelValue="handleDialogClose"
  >
    <template #default>
      <div class="p-4 flex flex-col items-center justify-center space-y-6">

        <div v-if="isInitialLoading" class="py-8 flex items-center justify-center">
          <div class="h-8 w-8 border-2 border-ink-blue-3 border-t-transparent rounded-full animate-spin" />
        </div>

        <div v-else-if="errorMessage" class="text-center py-4 text-ink-red-500 font-medium text-sm">
          {{ errorMessage }}
        </div>

        <div v-else-if="currentCode" class="w-full flex flex-col items-center space-y-6">
          <!-- QR Code (Only returned for Owners/Admins) -->
          <div v-if="currentQr" class="flex justify-center bg-surface-base p-2 rounded-xl shadow-sm border border-outline-gray-2" v-html="currentQr" />

          <!-- Code Display -->
          <div class="text-center">
            <div class="font-mono text-3xl font-bold tracking-[0.25em] text-ink-gray-9 select-all">
              {{ formattedCode }}
            </div>
          </div>

          <!-- Progress / Timer -->
          <div class="flex items-center gap-2 text-sm font-medium text-ink-gray-6">
            <div
              class="w-2.5 h-2.5 rounded-full shadow-inner transition-colors duration-300"
              :class="remainingSeconds > 5 ? 'bg-ink-blue-500' : 'bg-ink-red-500 animate-pulse'"
            />
            {{ remainingSeconds }} seconds remaining
          </div>
        </div>

      </div>
    </template>

    <template #actions>
      <div class="px-4 pb-4 flex justify-end gap-2">
        <Button variant="outline" @click="modelValue = false" class="text-ink-gray-7 hover:bg-surface-gray-2">
          Close
        </Button>
        <Button
          v-if="currentCode"
          :variant="copied ? 'outline' : 'solid'"
          :theme="copied ? 'green' : 'gray'"
          :icon-left="copied ? 'lucide-check' : 'lucide-copy'"
          @click="copyCode"
          class="font-semibold shadow-sm w-32"
        >
          {{ copied ? 'Copied!' : 'Copy Code' }}
        </Button>
      </div>
    </template>
  </Dialog>
</template>

<script setup>
import { computed, ref, watch, onUnmounted } from 'vue'
import { Dialog, Button, toast } from 'frappe-ui'
import { useGetTotp } from '../composables/vault'
import { useClipboard } from '../composables/clipboard'

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false
  },
  secretName: {
    type: String,
    required: true
  }
})

const emit = defineEmits(['update:modelValue'])

const modelValue = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val)
})

const totpResource = useGetTotp()
const { copy, copied } = useClipboard(3000)

const currentCode = ref('')
const currentQr = ref('')
const errorMessage = ref('')
const isInitialLoading = ref(true)

const remainingSeconds = ref(0)
let timerInterval = null

const formattedCode = computed(() => {
  const code = currentCode.value
  if (!code) return '------'
  return `${code.slice(0, 3)} ${code.slice(3)}`
})

function fetchTotp() {
  if (!props.secretName) return
  totpResource.submit({ name: props.secretName }).then(res => {
    isInitialLoading.value = false
    if (res?.code) {
      currentCode.value = res.code
      currentQr.value = res.qr_svg || ''
      errorMessage.value = ''
      remainingSeconds.value = res.remaining_seconds || 30
      startTimer()
    } else if (res?.error) {
      errorMessage.value = res.error
    }
  }).catch(err => {
    isInitialLoading.value = false
    errorMessage.value = err.message || 'Failed to fetch TOTP code.'
  })
}

function startTimer() {
  clearTimer()
  timerInterval = setInterval(() => {
    remainingSeconds.value--
    if (remainingSeconds.value <= 0) {
      clearTimer()
      fetchTotp()
    }
  }, 1000)
}

function clearTimer() {
  if (timerInterval) {
    clearInterval(timerInterval)
    timerInterval = null
  }
}

function handleDialogClose(val) {
  if (!val) {
    clearTimer()
  }
}

function copyCode() {
  if (currentCode.value) {
    copy(currentCode.value)
    toast.success('TOTP Code copied')
  }
}

watch(() => props.modelValue, (isOpen) => {
  if (isOpen) {
    isInitialLoading.value = true
    errorMessage.value = ''
    currentCode.value = ''
    currentQr.value = ''
    fetchTotp()
  } else {
    clearTimer()
  }
})

onUnmounted(() => {
  clearTimer()
})
</script>
