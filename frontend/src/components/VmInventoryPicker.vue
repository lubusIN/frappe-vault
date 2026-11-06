<template>
  <Dialog v-model="show" title="Add Hosts from Inventory" size="lg">
    <template #default>
      <div class="space-y-4">
        <!-- Step 1: server role -->
        <div v-if="!selectedRole">
          <p class="text-sm text-ink-gray-6 leading-normal mb-3">
            Choose a server role to see the machines tagged with it.
          </p>
          <div v-if="rolesResource.loading" class="text-sm text-ink-gray-5 py-6 text-center">Loading roles&hellip;</div>
          <div v-else-if="!roles.length" class="text-sm text-ink-gray-5 py-6 text-center">
            No VM inventory found.
          </div>
          <div v-else class="space-y-1.5">
            <button
              v-for="role in roles" :key="role.value"
              class="w-full flex items-center justify-between px-3 py-2.5 rounded-lg border border-outline-gray-1 hover:border-outline-gray-3 hover:bg-surface-gray-1 transition-colors text-left"
              @click="selectRole(role)"
            >
              <span class="text-sm font-medium text-ink-gray-9">{{ role.label }}</span>
              <span class="text-xs text-ink-gray-5">{{ role.count }} {{ role.count === 1 ? 'server' : 'servers' }}</span>
            </button>
          </div>
        </div>

        <!-- Step 2: pick VMs within that role -->
        <div v-else>
          <div class="flex items-center gap-2 mb-3">
            <Button variant="ghost" size="sm" icon="lucide-arrow-left" @click="selectedRole = null" />
            <p class="text-sm font-medium text-ink-gray-9">{{ selectedRole.label }}</p>
            <span class="text-xs text-ink-gray-5">({{ vms.length }})</span>
          </div>

          <FormControl
            v-if="vms.length > 8"
            v-model="filterText" placeholder="Filter by name or IP&hellip;"
            class="mb-3"
          />

          <div v-if="vmsResource.loading" class="text-sm text-ink-gray-5 py-6 text-center">Loading servers&hellip;</div>
          <div v-else-if="!filteredVms.length" class="text-sm text-ink-gray-5 py-6 text-center">No matches.</div>
          <div v-else class="space-y-1 max-h-80 overflow-y-auto pr-1">
            <label
              v-for="vm in filteredVms" :key="vm.name"
              class="flex items-center gap-3 px-3 py-2 rounded-lg"
              :class="vm.has_usable_ip ? 'hover:bg-surface-gray-1 cursor-pointer' : 'opacity-50 cursor-not-allowed'"
            >
              <input
                type="checkbox"
                :disabled="!vm.has_usable_ip || alreadyAdded.has(vm.ip)"
                :checked="selected.has(vm.name)"
                @change="toggleVm(vm)"
                class="rounded border-outline-gray-3"
              />
              <span class="flex-1 min-w-0 text-sm font-medium text-ink-gray-9 truncate">{{ vm.vm_name }}</span>
              <span v-if="vm.power_state && vm.power_state !== 'POWERED_ON'" class="text-xs text-ink-amber-6 shrink-0">{{ vm.power_state }}</span>
              <span v-if="vm.has_usable_ip" class="text-xs font-mono text-ink-gray-5 shrink-0">
                {{ vm.ip }}<span v-if="alreadyAdded.has(vm.ip)" class="text-ink-gray-4"> &middot; added</span>
              </span>
              <span v-else class="text-xs text-ink-red-3 shrink-0">no usable IP</span>
            </label>
          </div>
        </div>
      </div>
    </template>

    <template #actions>
      <div class="flex items-center justify-end gap-2 px-4 pb-4">
        <Button variant="outline" @click="show = false">Cancel</Button>
        <Button
          v-if="selectedRole"
          variant="solid" :disabled="selected.size === 0"
          @click="confirmAdd"
        >
          Add {{ selected.size || '' }} {{ selected.size === 1 ? 'Host' : 'Hosts' }}
        </Button>
      </div>
    </template>
  </Dialog>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { Dialog, FormControl, Button } from 'frappe-ui'
import { useVmServerRoles, useVmsForRole } from '../composables/vault'

const props = defineProps({
  modelValue: Boolean,
  // Hostnames/IPs already in the form, so the picker can show what's already
  // added instead of letting someone select the same server twice.
  existingHosts: { type: Array, default: () => [] },
})
const emit = defineEmits(['update:modelValue', 'add'])

const show = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})

const rolesResource = useVmServerRoles()
const vmsResource = useVmsForRole()

const roles = ref([])
const selectedRole = ref(null)
const vms = ref([])
const selected = ref(new Set())
const filterText = ref('')

const alreadyAdded = computed(() => new Set(props.existingHosts.filter(Boolean)))

const filteredVms = computed(() => {
  if (!filterText.value.trim()) return vms.value
  const q = filterText.value.trim().toLowerCase()
  return vms.value.filter(vm => vm.vm_name.toLowerCase().includes(q) || (vm.ip || '').includes(q))
})

watch(show, async (v) => {
  if (!v) {
    selectedRole.value = null
    vms.value = []
    selected.value = new Set()
    filterText.value = ''
    return
  }
  roles.value = (await rolesResource.submit()) || []
})

async function selectRole(role) {
  selectedRole.value = role
  selected.value = new Set()
  vms.value = (await vmsResource.submit({ server_role: role.value })) || []
}

function toggleVm(vm) {
  if (!vm.has_usable_ip || alreadyAdded.value.has(vm.ip)) return
  if (selected.value.has(vm.name)) selected.value.delete(vm.name)
  else selected.value.add(vm.name)
  // Trigger reactivity — Set mutations aren't tracked by Vue on their own.
  selected.value = new Set(selected.value)
}

function confirmAdd() {
  const hosts = vms.value
    .filter(vm => selected.value.has(vm.name))
    .map(vm => ({ hostname: vm.ip, ssh_port: '', label: vm.vm_name }))
  emit('add', hosts)
  show.value = false
}
</script>
