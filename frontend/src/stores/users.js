import { defineStore } from 'pinia'
import { createResource } from 'frappe-ui'
import { computed, reactive } from 'vue'

export const usersStore = defineStore('vault-users', () => {
  let usersByName = reactive({})

  const users = createResource({
    url: 'frappe_vault.api.session.get_users',
    cache: 'vault-users',
    initialData: [],
    auto: true,
    transform([allUsers, vaultUsers]) {
      allUsers = normalizeUsers(allUsers)
      vaultUsers = normalizeUsers(vaultUsers)
      for (let user of allUsers) {
        if (usersByName[user.name]) {
          Object.assign(usersByName[user.name], user)
        } else {
          usersByName[user.name] = user
        }
        if (user.name === 'Administrator') {
          if (usersByName[user.email]) {
            Object.assign(usersByName[user.email], user)
          } else {
            usersByName[user.email] = user
          }
        }
      }
      return { allUsers, vaultUsers }
    },
    onSuccess() {
      scheduleBackgroundFetch()
    },
  })

  const usersFull = createResource({
    url: 'frappe_vault.api.session.get_users',
    params: { include_all: 1 },
    cache: 'vault-users-full',
    auto: false,
    transform([allUsers]) {
      allUsers = normalizeUsers(allUsers)
      for (let user of allUsers) {
        const existing = usersByName[user.name]
        if (existing) {
          Object.assign(existing, user)
        } else {
          usersByName[user.name] = user
        }
      }
      return { allUsers }
    },
  })

  let backgroundFetchScheduled = false
  function scheduleBackgroundFetch() {
    if (backgroundFetchScheduled) return
    backgroundFetchScheduled = true
    const fire = () => usersFull.fetch()
    if (typeof requestIdleCallback === 'function') {
      requestIdleCallback(fire, { timeout: 5000 })
    } else {
      setTimeout(fire, 2000)
    }
  }

  const pendingResolves = new Set()
  let flushScheduled = false

  function queueResolve(email) {
    pendingResolves.add(email)
    if (flushScheduled) return
    flushScheduled = true
    queueMicrotask(flush)
  }

  async function flush() {
    flushScheduled = false
    if (!pendingResolves.size) return
    const batch = [...pendingResolves]
    pendingResolves.clear()
    try {
      const r = createResource({
        url: 'frappe_vault.api.session.get_user_info',
        params: { users: batch },
        auto: false,
      })
      const records = await r.fetch()
      for (const u of normalizeUsers(records || [])) {
        usersByName[u.name] = { ...usersByName[u.name], ...u }
      }
    } catch (e) {
      // best-effort
    }
  }

  function getUser(email) {
    if (!email || email === 'sessionUser') {
      email = window.frappe?.session?.user || ''
    }
    if (!usersByName[email]) {
      usersByName[email] = {
        name: email,
        email: email,
        full_name: email.split('@')[0],
        first_name: email.split('@')[0],
        last_name: '',
        user_image: null,
        role: null,
      }
      if (!usersFull.data) {
        queueResolve(email)
      }
    }
    return usersByName[email]
  }

  function isAdmin(email) {
    return getUser(email).role === 'Vault Admin'
  }

  function isVaultUser(email) {
    return getUser(email).role === 'Vault User'
  }

  function getUserRole(email) {
    const user = getUser(email)
    if (user && user.role) {
      return user.role
    }
    return null
  }

  return {
    users,
    usersFull,
    allUsers: computed(() => usersFull.data?.allUsers || users.data?.allUsers),
    vaultUsers: computed(() => users.data?.vaultUsers),
    getUser,
    isAdmin,
    isVaultUser,
    getUserRole,
  }
})

function normalizeUsers(users) {
  return (users || []).filter(Boolean).map((user) => normalizeUser(user))
}

function normalizeUser(user) {
  const name = user.name || user.email || ''
  const email = user.email || name
  const fallbackName = name || email

  return {
    ...user,
    name,
    email,
    full_name: user.full_name?.trim() || fallbackName,
  }
}
