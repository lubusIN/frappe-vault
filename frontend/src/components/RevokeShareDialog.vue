<template>
  <Dialog
    :modelValue="modelValue"
    title="Revoke Share Access"
    size="sm"
    @update:modelValue="val => emit('update:modelValue', val)"
  >
    <template #default>
      <div class="pt-2">
        <p class="text-sm text-ink-gray-7">
          Are you sure you want to revoke share access for
          <span class="font-bold text-ink-gray-9">{{ shareTargetName }}</span>
          <template v-if="itemTitle"> on {{ itemType }} <span class="font-bold text-ink-gray-9">"{{ itemTitle }}"</span></template>?
        </p>
      </div>
    </template>
    <template #actions>
      <div class="flex justify-end gap-2 px-4 pb-4">
        <Button variant="ghost" label="Cancel" @click="emit('update:modelValue', false)" class="text-ink-gray-7 focus:outline-none" />
        <Button
          variant="solid"
          theme="red"
          label="Revoke Access"
          :loading="isRevoking"
          @click="handleRevoke"
          class="px-4 font-semibold shadow-sm focus:outline-none"
        />
      </div>
    </template>
  </Dialog>
</template>

<script setup>
import { ref, computed } from 'vue'
import { Dialog, Button, toast } from 'frappe-ui'
import { useUnshare } from '../composables/vault'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  share: { type: Object, default: null },
})

const emit = defineEmits(['update:modelValue', 'revoked'])

const isRevoking = ref(false)
const unshareResource = useUnshare()

const shareTargetName = computed(() => {
  if (!props.share) return ''
  if (props.share.share_type === 'User') {
    return props.share.user || props.share.shared_with || ''
  }
  return props.share.frappe_role || props.share.user || ''
})

const itemTitle = computed(() => {
  if (!props.share) return ''
  if (typeof props.share.title === 'object' && props.share.title !== null) {
    return props.share.title.title || ''
  }
  return props.share.title || props.share.shared_name || ''
})

const itemType = computed(() => {
  return props.share?.shared_doctype === 'Vault Folder' ? 'folder' : 'secret'
})

async function handleRevoke() {
  if (!props.share) return
  isRevoking.value = true
  try {
    const shareName = props.share.name || props.share.share_name
    await unshareResource.submit({ share_name: shareName })
    toast.success('Share access revoked successfully')
    emit('update:modelValue', false)
    emit('revoked')
  } catch (err) {
    toast.error(err.messages?.[0] || err.message || 'Failed to revoke access')
  } finally {
    isRevoking.value = false
  }
}
</script>
