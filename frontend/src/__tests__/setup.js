import { vi } from 'vitest'

// Mock frappe-ui so components importing from 'frappe-ui' mount cleanly in Vitest jsdom
vi.mock('frappe-ui', () => {
  return {
    Badge: {
      name: 'Badge',
      props: ['variant', 'size', 'theme', 'label'],
      template: '<span class="frappe-badge" :data-theme="theme" :data-variant="variant"><slot>{{ label }}</slot></span>',
    },
    Button: {
      name: 'Button',
      props: ['variant', 'icon', 'label', 'loading'],
      template: '<button class="frappe-button" :data-variant="variant"><slot>{{ label }}</slot></button>',
    },
    Tooltip: {
      name: 'Tooltip',
      props: ['text'],
      template: '<div class="frappe-tooltip"><slot /></div>',
    },
    TextInput: {
      name: 'TextInput',
      props: ['modelValue', 'label', 'placeholder', 'type', 'disabled'],
      emits: ['update:modelValue'],
      template: '<input class="frappe-text-input" :value="modelValue" :disabled="disabled" @input="$emit(\'update:modelValue\', $event.target.value)" />',
    },
    Select: {
      name: 'Select',
      props: ['modelValue', 'options'],
      emits: ['update:modelValue'],
      template: '<select class="frappe-select" :value="modelValue" @change="$emit(\'update:modelValue\', $event.target.value)"><option v-for="opt in options" :key="opt.value" :value="opt.value">{{ opt.label }}</option></select>',
    },
    Combobox: {
      name: 'Combobox',
      props: ['modelValue', 'options', 'placeholder'],
      emits: ['update:modelValue'],
      template: '<div class="frappe-combobox"><slot /></div>',
    },
    Switch: {
      name: 'Switch',
      props: ['modelValue'],
      emits: ['update:modelValue'],
      template: '<button class="frappe-switch" :data-active="modelValue" @click="$emit(\'update:modelValue\', !modelValue)"></button>',
    },
    Checkbox: {
      name: 'Checkbox',
      props: ['modelValue'],
      emits: ['update:modelValue'],
      template: '<input type="checkbox" class="frappe-checkbox" :checked="modelValue" @change="$emit(\'update:modelValue\', $event.target.checked)" />',
    },
    TextEditor: {
      name: 'TextEditor',
      props: ['content', 'fixedMenu'],
      emits: ['change'],
      template: '<div class="frappe-text-editor" :data-content="content"></div>',
    },
    createDocumentResource: vi.fn(() => ({
      doc: {
        name: '',
        subject: '',
        response: '',
        response_html: '',
        use_html: 0,
        vault_enabled: 0,
        vault_is_default: 0,
      },
      get: { submit: vi.fn() },
      insert: { submit: vi.fn() },
      setValue: { submit: vi.fn() },
    })),
    toast: {
      success: vi.fn(),
      error: vi.fn(),
    },
  }
})
