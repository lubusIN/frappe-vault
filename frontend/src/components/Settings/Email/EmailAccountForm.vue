<template>
  <div class="flex flex-col h-full bg-surface-elevation-2">
    <!-- Form Content -->
    <div class="flex-1 overflow-y-auto px-4 py-4">
      <div v-if="account.doc" class="max-w-2xl">
        <div class="flex flex-col gap-1 mb-6">
          <h2 class="text-2xl font-semibold text-ink-gray-8">Setup Email</h2>
          <p class="text-sm text-ink-gray-5">Choose the email service provider you want to configure.</p>
        </div>

        <div class="flex flex-wrap items-center gap-2 mb-6">
          <div
            v-for="prov in providers"
            :key="prov.name"
            class="flex flex-col items-center gap-1 w-[70px] cursor-pointer"
            @click="selectProvider(prov.name)"
          >
            <div 
              class="flex items-center justify-center w-8 h-8 bg-surface-gray-2 rounded-xl transition-all hover:bg-surface-gray-3"
              :class="{ 'ring-2 ring-outline-gray-4': account.doc?.service === prov.name }"
            >
              <img :src="prov.icon" :alt="prov.label" class="w-4 h-4 object-contain" />
            </div>
            <p class="text-xs text-center text-ink-gray-6 mt-1">{{ prov.label }}</p>
          </div>
        </div>

        <!-- Dynamic Warning Info Alert -->
        <div v-if="currentProvider?.helpLink" class="flex items-start gap-2 p-3 mb-6 bg-surface-gray-2 border border-outline-gray-3 rounded-lg text-sm text-ink-gray-7">
          <FeatherIcon name="info" class="w-4 h-4 mt-0.5 shrink-0 text-ink-gray-5" />
          <span>{{ currentProvider.infoPrefix }} <a :href="currentProvider.helpLink" target="_blank" class="text-ink-blue-5 hover:underline">here</a>.</span>
        </div>

        <div class="flex flex-col gap-4">

        <FormControl
          label="Account Name"
          type="text"
          v-model="account.doc.email_account_name"
          placeholder="Support / Sales"
          :error-message="validationErrors.email_account_name"
          @update:modelValue="validateFields"
        />

        <FormControl
          label="Email ID"
          type="email"
          v-model="account.doc.email_id"
          placeholder="johndoe@example.com"
          :error-message="validationErrors.email_id"
          @update:modelValue="validateFields"
        />

        <template v-if="account.doc.service !== 'Frappe Mail'">
          <FormControl
            label="Password"
            type="password"
            v-model="account.doc.password"
            placeholder="••••••••"
            :error-message="validationErrors.password"
            @update:modelValue="validateFields"
          />
        </template>

        <template v-else>
          <FormControl
            label="Frappe Mail Site"
            type="text"
            v-model="account.doc.frappe_mail_site"
            placeholder="https://frappemail.com"
          />

          <FormControl
            label="API Key"
            type="text"
            v-model="account.doc.api_key"
            placeholder="••••••••"
            :error-message="validationErrors.api_key"
            @update:modelValue="validateFields"
          />

          <FormControl
            label="API Secret"
            type="password"
            v-model="account.doc.api_secret"
            placeholder="••••••••"
            :error-message="validationErrors.api_secret"
            @update:modelValue="validateFields"
          />
        </template>

        <div class="grid grid-cols-1 sm:grid-cols-2 gap-6 mt-2">
          <!-- Incoming Settings -->
          <div class="flex flex-col gap-5">
            <FormControl
              type="checkbox"
              label="Enable Incoming"
              v-model="account.doc.enable_incoming"
            />
            <div class="text-xs text-ink-gray-5 leading-relaxed -mt-3 ml-6">If enabled, emails will be pulled from this account.</div>
            
            <FormControl
              type="checkbox"
              label="Default Incoming"
              v-model="account.doc.default_incoming"
              :disabled="!account.doc.enable_incoming"
            />
            <div class="text-xs text-ink-gray-5 leading-relaxed -mt-3 ml-6">If enabled, all replies to your company (eg: replies@yourcompany.com) will come to this account. Note: Only one account can be default incoming.</div>
          </div>

          <!-- Outgoing Settings -->
          <div class="flex flex-col gap-5">
            <FormControl
              type="checkbox"
              label="Enable Outgoing"
              v-model="account.doc.enable_outgoing"
            />
            <div class="text-xs text-ink-gray-5 leading-relaxed -mt-3 ml-6">If enabled, outgoing emails can be sent from this account.</div>

            <FormControl
              type="checkbox"
              label="Default Outgoing"
              v-model="account.doc.default_outgoing"
              :disabled="!account.doc.enable_outgoing"
            />
            <div class="text-xs text-ink-gray-5 leading-relaxed -mt-3 ml-6">If enabled, all outgoing emails will be sent from this account. Note: Only one account can be default outgoing.</div>
          </div>
        </div>
        </div>
        
        <!-- Action Buttons -->
        <div class="flex items-center justify-between mt-10">
          <Button
            variant="outline"
            label="Back"
            @click="$emit('back')"
          />
          <Button
            variant="solid"
            :label="accountId ? 'Save Changes' : 'Create'"
            :loading="isSaving"
            @click="saveAccount"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed, reactive } from 'vue'
import { Button, FormControl, FeatherIcon, createResource, toast } from 'frappe-ui'

import gmailIcon from '../../../../public/images/gmail.png'
import outlookIcon from '../../../../public/images/outlook.png'
import sendgridIcon from '../../../../public/images/sendgrid.png'
import sparkpostIcon from '../../../../public/images/sparkpost.webp'
import yahooIcon from '../../../../public/images/yahoo.png'
import yandexIcon from '../../../../public/images/yandex.png'
import frappeMailIcon from '../../../../public/images/frappe-mail.svg'

const props = defineProps({
  accountId: { type: String, default: null }
})

const emit = defineEmits(['back', 'saved'])

const isSaving = ref(false)
const showValidations = ref(false)

const validationErrors = reactive({
  email_account_name: '',
  email_id: '',
  password: '',
  api_key: '',
  api_secret: ''
})

const providers = [
  { label: 'GMail', name: 'GMail', icon: gmailIcon, helpLink: 'https://support.google.com/accounts/answer/185833', infoPrefix: 'Setting up GMail requires you to enable two factor authentication and app specific passwords. Read more' },
  { label: 'Outlook', name: 'Outlook.com', icon: outlookIcon, helpLink: 'https://support.microsoft.com/en-us/account-billing/how-to-get-and-use-app-passwords-5896ed9b-4263-e681-128a-a6f2979a7944', infoPrefix: 'Setting up Outlook.com requires you to enable two factor authentication and app specific passwords. Read more' },
  { label: 'Sendgrid', name: 'Sendgrid', icon: sendgridIcon, helpLink: 'https://docs.sendgrid.com/ui/account-and-settings/api-keys', infoPrefix: 'Setting up Sendgrid requires you to enable two factor authentication and app specific passwords. Read more' },
  { label: 'SparkPost', name: 'SparkPost', icon: sparkpostIcon, helpLink: 'https://support.sparkpost.com/docs/my-account-and-profile/enabling-two-factor-authentication', infoPrefix: 'Setting up SparkPost requires you to enable two factor authentication and app specific passwords. Read more' },
  { label: 'Yahoo', name: 'Yahoo', icon: yahooIcon, helpLink: 'https://help.yahoo.com/kb/SLN15241.html', infoPrefix: 'Setting up Yahoo requires you to enable two factor authentication and app specific passwords. Read more' },
  { label: 'Yandex', name: 'Yandex', icon: yandexIcon, helpLink: 'https://yandex.com/support/id/authorization/app-passwords.html', infoPrefix: 'Setting up Yandex requires you to enable two factor authentication and app specific passwords. Read more' },
  { label: 'Frappe Mail', name: 'Frappe Mail', icon: frappeMailIcon, helpLink: 'https://github.com/frappe/mail', infoPrefix: 'Setting up Frappe Mail requires you to have an API key and API secret for your email account. Read more' }
]

const account = createResource({
  url: props.accountId ? 'frappe.client.get' : null,
  makeParams() {
    return {
      doctype: 'Email Account',
      name: props.accountId
    }
  },
  auto: !!props.accountId,
  onSuccess(data) {
    if (!account.doc) {
      account.doc = data
    }
  }
})

const currentProvider = computed(() => {
  return providers.find(p => p.name === account.doc?.service)
})

onMounted(() => {
  if (!props.accountId) {
    account.doc = {
      doctype: 'Email Account',
      email_account_name: '',
      email_id: '',
      password: '',
      api_key: '',
      api_secret: '',
      frappe_mail_site: '',
      service: 'GMail',
      enable_incoming: 1,
      enable_outgoing: 1,
      default_incoming: 0,
      default_outgoing: 0
    }
  }
})

function selectProvider(name) {
  if (account.doc) {
    account.doc.service = name
  }
}

function validateFields() {
  if (!showValidations.value) return true
  
  let isValid = true
  validationErrors.email_account_name = ''
  validationErrors.email_id = ''
  validationErrors.password = ''

  if (!account.doc.email_account_name) {
    validationErrors.email_account_name = 'Account name is required'
    isValid = false
  }
  if (!account.doc.email_id) {
    validationErrors.email_id = 'Email ID is required'
    isValid = false
  } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(account.doc.email_id)) {
    validationErrors.email_id = 'Valid email is required'
    isValid = false
  }
  if (account.doc.service !== 'Frappe Mail') {
    if (!account.doc.password) {
      validationErrors.password = 'Password is required'
      isValid = false
    }
  } else {
    if (!account.doc.api_key) {
      validationErrors.api_key = 'API key is required'
      isValid = false
    }
    if (!account.doc.api_secret) {
      validationErrors.api_secret = 'API secret is required'
      isValid = false
    }
  }

  return isValid
}

const emailServiceConfig = {
  "Frappe Mail": {
    "domain": null,
    "password": null,
    "awaiting_password": 0,
    "ascii_encode_password": 0,
    "login_id_is_different": 0,
    "login_id": null,
    "use_imap": 0,
    "use_ssl": 0,
    "validate_ssl_certificate": 0,
    "use_starttls": 0,
    "email_server": null,
    "incoming_port": 0,
    "always_use_account_email_id_as_sender": 1,
    "use_tls": 0,
    "use_ssl_for_outgoing": 0,
    "smtp_server": null,
    "smtp_port": null,
    "no_smtp_authentication": 0,
  },
  "GMail": {
    "email_server": "imap.gmail.com",
    "use_ssl": 1,
    "smtp_server": "smtp.gmail.com",
  },
  "Outlook.com": {
    "email_server": "imap-mail.outlook.com",
    "use_ssl": 1,
    "smtp_server": "smtp-mail.outlook.com",
  },
  "Sendgrid": {
    "smtp_server": "smtp.sendgrid.net",
    "smtp_port": 587,
  },
  "SparkPost": {
    "smtp_server": "smtp.sparkpostmail.com",
  },
  "Yahoo": {
    "email_server": "imap.mail.yahoo.com",
    "use_ssl": 1,
    "smtp_server": "smtp.mail.yahoo.com",
    "smtp_port": 587,
  },
  "Yandex": {
    "email_server": "imap.yandex.com",
    "use_ssl": 1,
    "smtp_server": "smtp.yandex.com",
    "smtp_port": 587,
  }
}

async function saveAccount() {
  showValidations.value = true
  if (!validateFields()) {
    return
  }
  
  isSaving.value = true
  try {
    const serviceConfig = emailServiceConfig[account.doc.service] || {}
    const docToSave = {
      ...account.doc,
      email_sync_option: "ALL",
      initial_sync_count: 100,
      use_imap: 1,
      use_tls: 1,
      smtp_port: 587,
      imap_folder: [{ folder_name: 'INBOX' }],
      ...serviceConfig
    }

    if (props.accountId && props.accountId !== account.doc.email_account_name) {
      const renameRes = createResource({
        url: 'frappe.client.rename_doc',
        makeParams() {
          return {
            doctype: 'Email Account',
            old_name: props.accountId,
            new_name: account.doc.email_account_name
          }
        }
      })
      await renameRes.fetch()
      docToSave.name = account.doc.email_account_name
      
      const getRes = createResource({
        url: 'frappe.client.get',
        makeParams() {
          return {
            doctype: 'Email Account',
            name: account.doc.email_account_name
          }
        }
      })
      const latestDoc = await getRes.fetch()
      docToSave.modified = latestDoc.modified
    }

    const saveRes = createResource({
      url: 'frappe.client.save',
      makeParams() {
        return {
          doc: JSON.stringify(docToSave)
        }
      }
    })
    await saveRes.fetch()
    toast.success(`Account ${props.accountId ? 'updated' : 'created'} successfully!`)
    emit('saved')
  } catch (err) {
    toast.error(err.message || 'Failed to save account.')
  } finally {
    isSaving.value = false
  }
}
</script>
