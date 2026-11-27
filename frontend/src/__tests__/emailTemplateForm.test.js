import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import EmailTemplateForm from '@/components/Settings/Email/EmailTemplateForm.vue'

describe('EmailTemplateForm.vue Component Tests', () => {
  it('renders "New Template" heading when no templateId is provided', () => {
    const wrapper = mount(EmailTemplateForm, {
      props: {
        templateId: null,
      },
    })

    expect(wrapper.text()).toContain('New Template')
    expect(wrapper.find('h2').text()).toBe('New Template')
  })

  it('renders "Edit Template" heading when templateId prop is passed', () => {
    const wrapper = mount(EmailTemplateForm, {
      props: {
        templateId: 'Vault Invitation Default',
      },
    })

    expect(wrapper.find('h2').text()).toBe('Edit Template')
  })

  it('emits "back" event when the back arrow button is clicked', async () => {
    const wrapper = mount(EmailTemplateForm, {
      props: {
        templateId: null,
      },
    })

    const backButton = wrapper.find('button[data-variant="ghost"]')
    await backButton.trigger('click')

    expect(wrapper.emitted('back')).toBeTruthy()
    expect(wrapper.emitted('back').length).toBe(1)
  })

  it('displays required validation errors when saving with empty name and subject', async () => {
    const wrapper = mount(EmailTemplateForm, {
      props: {
        templateId: null,
      },
    })

    // Find save button (solid variant)
    const saveButton = wrapper.find('button[data-variant="solid"]')
    await saveButton.trigger('click')

    expect(wrapper.text()).toContain('Name is required')
    expect(wrapper.text()).toContain('Subject is required')
  })

  it('allows toggling between Rich Text editor and raw HTML textarea', async () => {
    const wrapper = mount(EmailTemplateForm, {
      props: {
        templateId: null,
      },
    })

    // Initially "Rich Text" is selected
    expect(wrapper.find('.frappe-text-editor').exists()).toBe(true)
    expect(wrapper.find('textarea').exists()).toBe(false)

    // Switch to HTML
    const select = wrapper.find('.frappe-select')
    await select.setValue('HTML')

    expect(wrapper.find('textarea').exists()).toBe(true)
    expect(wrapper.find('.frappe-text-editor').exists()).toBe(false)
  })
})

