import { DATABASE_TYPES } from './constants'

// Field descriptors rendered by NewSecretDialog and SecretDetailsPanel.
//
//   type      'text' | 'email' | 'url' | 'password' | 'textarea' | 'file'
//             | 'select' (needs `options`) | 'checkbox'
//   showIf    optional predicate on the whole form — a field that is only
//             meaningful for some other field's value, e.g. MongoDB's auth source
//
export const secretFieldsConfig = {
  'Password': [
    { name: 'url', label: 'URL', type: 'url', isLink: true, colSpan: 2, placeholder: 'https://...' },
    { name: 'username', label: 'Username', type: 'text', mono: true, colSpan: 1 },
    { name: 'email', label: 'Email', type: 'email', mono: true, colSpan: 1 },
    { name: 'password', label: 'Password', type: 'password', mono: true, colSpan: 2 },
    { name: 'totp_secret', label: 'TOTP Secret (2FA)', type: 'password', mono: true, placeholder: 'Base32 Seed', colSpan: 2 }
  ],
  'API Key': [
    { name: 'url', label: 'Endpoint URL', type: 'url', isLink: true, colSpan: 2 },
    { name: 'api_key', label: 'API Key', type: 'text', mono: true, colSpan: 2 },
    { name: 'api_secret', label: 'API Secret', type: 'password', mono: true, colSpan: 2 },
    { name: 'totp_secret', label: 'TOTP Secret (2FA)', type: 'password', mono: true, placeholder: 'Base32 Seed', colSpan: 2 }
  ],
  'Credit Card': [
    { name: 'card_holder', label: 'Card Holder', type: 'text', mono: false, colSpan: 2 },
    { name: 'card_number', label: 'Card Number', type: 'password', mono: true, placeholder: '•••• •••• •••• ••••', colSpan: 2 },
    { name: 'card_expiry', label: 'Expiry', type: 'text', mono: true, placeholder: 'MM/YY', colSpan: 1 },
    { name: 'card_cvv', label: 'CVV', type: 'password', mono: true, placeholder: '123', colSpan: 1 }
  ],
  'Database': [
    { name: 'database_type', label: 'Database Type', type: 'select', options: DATABASE_TYPES, colSpan: 2 },
    { name: 'url', label: 'URL', type: 'url', isLink: true, colSpan: 2 },
    { name: 'db_host', label: 'Host', type: 'text', mono: true, placeholder: 'localhost or IP', colSpan: 1 },
    { name: 'db_port', label: 'Port', type: 'text', mono: true, placeholder: 'Engine default', colSpan: 1 },
    { name: 'db_name', label: 'DB Name', type: 'text', mono: false, colSpan: 1 },
    { name: 'username', label: 'Username', type: 'text', mono: true, colSpan: 1 },
    { name: 'db_password', label: 'Password', type: 'password', mono: true, colSpan: 2 },
    {
      name: 'db_auth_source',
      label: 'Auth Source',
      type: 'text',
      mono: true,
      placeholder: 'admin',
      colSpan: 1,
      showIf: (form) => form.database_type === 'MongoDB',
    },
    { name: 'db_use_ssl', label: 'Use TLS / SSL', type: 'checkbox', colSpan: 1 }
  ],
  'Linux Server': [
    { name: 'username', label: 'Account', type: 'text', mono: true, placeholder: 'the Unix account to rotate', colSpan: 1 },
    { name: 'ansible_user', label: 'Ansible User', type: 'text', mono: true, colSpan: 1 },
    { name: 'password', label: 'Password', type: 'password', mono: true, colSpan: 2 }
  ],
  'SSH Key': [
    { name: 'url', label: 'URL / Server IP', type: 'url', isLink: true, colSpan: 2 },
    { name: 'username', label: 'Username', type: 'text', mono: true, placeholder: 'root / ubuntu', colSpan: 2 },
    { name: 'ssh_private_key', label: 'SSH Private Key', type: 'textarea', mono: true, placeholder: '-----BEGIN OPENSSH PRIVATE KEY-----...', colSpan: 2 }
  ],
  'Media': [
    { name: 'url', label: 'URL', type: 'url', isLink: true, colSpan: 2 },
    { name: 'attachment', label: 'Attachment', type: 'file', colSpan: 2 }
  ],
  'Note': [
    { name: 'url', label: 'URL', type: 'url', isLink: true, colSpan: 2 }
  ],
  'Other': [
    { name: 'url', label: 'URL', type: 'url', isLink: true, colSpan: 2 }
  ]
}

// Fields a form should actually render for `secretType`, given current values.
export function visibleFieldsFor(secretType, form) {
  return (secretFieldsConfig[secretType] || []).filter(
    (field) => !field.showIf || field.showIf(form || {})
  )
}
