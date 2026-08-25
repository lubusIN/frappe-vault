<template>
  <div class="flex flex-col h-full p-4 rounded-r-lg">
    <div class="px-4 py-3">
      <h2 class="text-xl font-semibold text-ink-gray-9 mb-1">Appearance</h2>
      <p class="text-sm text-ink-gray-5">Customize the look and feel of the application.</p>
    </div>

    <div class="flex-1 overflow-y-auto px-4 mt-6">
      <div class="flex flex-col gap-6">

        <ThemeSwitcher
          name="Vault"
          logo="/assets/frappe_vault/images/vault-icon.svg"
          label="Theme"
          description="Switch between light, dark, or system theme"
        />

      </div>
    </div>
  </div>
</template>

<script setup>
import { ThemeSwitcher } from 'frappe-ui'
</script>
