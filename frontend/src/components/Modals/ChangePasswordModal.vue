<template>
  <Dialog
    v-model="isOpen"
    :options="{ title: 'Change Password', size: 'sm' }"
  >
    <template #body-content>
      <form class="space-y-4" @submit.prevent="savePassword">
        <FormControl
          label="Old Password"
          type="password"
          v-model="oldPassword"
          placeholder="Enter current password"
          :error="oldPasswordError"
        />
        <FormControl
          label="New Password"
          type="password"
          v-model="newPassword"
          placeholder="Enter new password"
          :error="newPasswordError"
        />
        <FormControl
          label="Confirm Password"
          type="password"
          v-model="confirmPassword"
          placeholder="Confirm new password"
          :error="confirmPasswordError"
          @keyup.enter="savePassword"
        />
      </form>
    </template>
    <template #actions>
      <div class="flex justify-end gap-2">
        <Button variant="ghost" label="Cancel" @click="isOpen = false" />
        <Button
          variant="solid"
          label="Save"
          :loading="loading"
          :disabled="!isValid"
          @click="savePassword"
        />
      </div>
    </template>
  </Dialog>
</template>

<script setup>
import { ref, computed } from 'vue'
import { Dialog, FormControl, Button, toast, call } from 'frappe-ui'

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['update:modelValue'])

const isOpen = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val)
})

const oldPassword = ref('')
const newPassword = ref('')
const confirmPassword = ref('')
const loading = ref(false)

const showValidation = ref(false)

const oldPasswordError = computed(() => {
  if (!showValidation.value) return ''
  if (!oldPassword.value) return 'Current password is required'
  return ''
})

const newPasswordError = computed(() => {
  if (!showValidation.value) return ''
  if (!newPassword.value) return 'New password is required'
  if (newPassword.value.length < 8) return 'Password must be at least 8 characters'
  return ''
})

const confirmPasswordError = computed(() => {
  if (!showValidation.value) return ''
  if (!confirmPassword.value) return 'Please confirm your password'
  if (confirmPassword.value !== newPassword.value) return 'Passwords do not match'
  return ''
})

const isValid = computed(() => {
  return (
    oldPassword.value &&
    newPassword.value &&
    newPassword.value.length >= 8 &&
    confirmPassword.value &&
    newPassword.value === confirmPassword.value
  )
})

async function savePassword() {
  showValidation.value = true
  if (!isValid.value) return
  
  loading.value = true
  try {
    const res = await call('frappe_vault.api.user.change_password', {
      new_password: newPassword.value,
      old_password: oldPassword.value,
    })
    
    if (res.message || res) {
      toast.success('Password changed successfully')
      isOpen.value = false
    }
  } catch (err) {
    const msg = err.messages?.[0] || err.message || 'Failed to change password'
    toast.error(msg)
  } finally {
    loading.value = false
  }
}
</script>
