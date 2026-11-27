import { vi } from 'vitest'

export const Badge = {
  name: 'Badge',
  props: ['variant', 'size', 'theme', 'label'],
  template: '<span class="frappe-badge" :data-theme="theme" :data-variant="variant"><slot>{{ label }}</slot></span>',
}

export const Button = {
  name: 'Button',
  props: ['variant', 'icon', 'label', 'loading'],
  template: '<button class="frappe-button" :data-variant="variant"><slot>{{ label }}</slot></button>',
}

export const Tooltip = {
  name: 'Tooltip',
  props: ['text'],
  template: '<div class="frappe-tooltip"><slot /></div>',
}

export const TextInput = {
  name: 'TextInput',
  props: ['modelValue', 'label', 'placeholder', 'type', 'disabled'],
  emits: ['update:modelValue'],
  template: '<input class="frappe-text-input" :value="modelValue" :disabled="disabled" @input="$emit(\'update:modelValue\', $event.target.value)" />',
}

export const Select = {
  name: 'Select',
  props: ['modelValue', 'options'],
  emits: ['update:modelValue'],
  template: '<select class="frappe-select" :value="modelValue" @change="$emit(\'update:modelValue\', $event.target.value)"><option v-for="opt in options" :key="opt.value" :value="opt.value">{{ opt.label }}</option></select>',
}

export const Combobox = {
  name: 'Combobox',
  props: ['modelValue', 'options', 'placeholder'],
  emits: ['update:modelValue'],
  template: '<div class="frappe-combobox"><slot /></div>',
}

export const Switch = {
  name: 'Switch',
  props: ['modelValue'],
  emits: ['update:modelValue'],
  template: '<button class="frappe-switch" :data-active="modelValue" @click="$emit(\'update:modelValue\', !modelValue)"></button>',
}

export const Checkbox = {
  name: 'Checkbox',
  props: ['modelValue'],
  emits: ['update:modelValue'],
  template: '<input type="checkbox" class="frappe-checkbox" :checked="modelValue" @change="$emit(\'update:modelValue\', $event.target.checked)" />',
}

export const TextEditor = {
  name: 'TextEditor',
  props: ['content', 'fixedMenu'],
  emits: ['change'],
  template: '<div class="frappe-text-editor" :data-content="content"></div>',
}

export const Dialog = {
  name: 'Dialog',
  props: ['modelValue', 'title', 'size'],
  emits: ['update:modelValue'],
  template: '<div class="frappe-dialog" v-if="modelValue"><slot /><slot name="actions" /></div>',
}

export const FormControl = {
  name: 'FormControl',
  props: ['modelValue', 'label', 'type', 'options', 'required', 'placeholder', 'rows'],
  emits: ['update:modelValue'],
  template: '<div class="frappe-form-control"><label>{{ label }}</label><input :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" /></div>',
}

export const Dropdown = {
  name: 'Dropdown',
  props: ['options'],
  template: '<div class="frappe-dropdown"><slot /></div>',
}

export const createDocumentResource = vi.fn(() => ({
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
}))

export const createResource = vi.fn(() => ({
  data: null,
  loading: false,
  fetch: vi.fn(),
  reload: vi.fn(),
  submit: vi.fn(),
}))

export const toast = {
  success: vi.fn(),
  error: vi.fn(),
}

