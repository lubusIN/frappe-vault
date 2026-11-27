import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import StrengthBadge from '@/components/StrengthBadge.vue'
import SecretTypeIcon from '@/components/SecretTypeIcon.vue'

describe('UI Component Unit Tests', () => {
  describe('StrengthBadge.vue', () => {
    it('renders "Unknown" and default gray theme when no strength is provided', () => {
      const wrapper = mount(StrengthBadge, {
        props: { strength: '' },
      })

      expect(wrapper.text()).toBe('Unknown')
      expect(wrapper.find('.frappe-badge').attributes('data-theme')).toBe('gray')
    })

    it('maps strength "Excellent" to green theme', () => {
      const wrapper = mount(StrengthBadge, {
        props: { strength: 'Excellent' },
      })

      expect(wrapper.text()).toBe('Excellent')
      expect(wrapper.find('.frappe-badge').attributes('data-theme')).toBe('green')
    })

    it('maps strength "Weak" to red theme', () => {
      const wrapper = mount(StrengthBadge, {
        props: { strength: 'Weak' },
      })

      expect(wrapper.text()).toBe('Weak')
      expect(wrapper.find('.frappe-badge').attributes('data-theme')).toBe('red')
    })
  })

  describe('SecretTypeIcon.vue', () => {
    it('renders Password secret type with key icon and label when showLabel is true', () => {
      const wrapper = mount(SecretTypeIcon, {
        props: {
          type: 'Password',
          showLabel: true,
        },
        global: {
          stubs: {
            Icon: {
              template: '<i :data-name="name"></i>',
              props: ['name'],
            },
          },
        },
      })

      expect(wrapper.find('i').attributes('data-name')).toBe('key')
      expect(wrapper.text()).toContain('Password')
    })

    it('renders custom label if passed instead of default type', () => {
      const wrapper = mount(SecretTypeIcon, {
        props: {
          type: 'API Key',
          showLabel: true,
          label: 'Custom API Token',
        },
        global: {
          stubs: {
            Icon: {
              template: '<i :data-name="name"></i>',
              props: ['name'],
            },
          },
        },
      })

      expect(wrapper.text()).toContain('Custom API Token')
    })
  })
})
