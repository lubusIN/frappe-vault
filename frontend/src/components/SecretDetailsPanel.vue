<template>
  <article class="space-y-2">
    <div class="flex items-center justify-between cursor-pointer select-none group" @click="detailsOpen = !detailsOpen">
      <h3 class="text-xs font-semibold text-ink-gray-5 uppercase tracking-wider group-hover:text-ink-gray-7 transition-colors">Secret Data</h3>
      <FeatherIcon name="chevron-down" class="w-4 h-4 text-ink-gray-4 transition-transform duration-200" :class="{ '-rotate-90': !detailsOpen }" />
    </div>
    <div v-show="detailsOpen" class="space-y-4 pt-2">
      <!-- EDIT VIEW FORM -->
      <div v-if="isEditing" class="space-y-4 pt-1 px-6">
        <!-- Title -->
        <div class="flex items-center justify-between gap-3 text-sm">
          <label class="w-28 shrink-0 text-ink-gray-5 font-normal">Title <span class="text-ink-red-3">*</span></label>
          <div class="flex-1 min-w-0">
            <TextInput v-model="editForm.title" placeholder="Secret Title" class="w-full text-sm" />
          </div>
        </div>

        <!-- Type select -->
        <div class="flex items-center justify-between gap-3 text-sm">
          <label class="w-28 shrink-0 text-ink-gray-5 font-normal">Type</label>
          <div class="flex-1 min-w-0">
            <FormControl v-model="editForm.secret_type" type="select" :options="secretTypeOptions" class="w-full text-sm cursor-pointer" />
          </div>
        </div>

        <!-- Folder select -->
        <div class="flex items-center justify-between gap-3 text-sm">
          <label class="w-28 shrink-0 text-ink-gray-5 font-normal">Folder</label>
          <div class="flex-1 min-w-0">
            <FormControl v-model="editForm.folder" type="select" :options="folderOptions" class="w-full text-sm cursor-pointer" />
          </div>
        </div>

        <div class="w-full border-t border-outline-gray-1 my-2" />

        <!-- Dynamic type inputs -->
        <div class="space-y-3">
          <template v-for="field in visibleFieldsFor(editForm.secret_type, editForm)" :key="field.name">
            <!-- Textarea -->
            <div v-if="field.type === 'textarea'" class="pt-1">
              <FormControl type="textarea" :label="field.label" v-model="editForm[field.name]" :rows="5" :placeholder="field.placeholder" class="w-full text-xs" :class="field.mono ? 'font-mono' : ''" />
            </div>

            <!-- File Attachment Edit Input -->
            <div v-else-if="field.type === 'file'" class="space-y-2 pt-1">
              <label class="block text-xs font-semibold text-ink-gray-5 uppercase tracking-wider">{{ field.label }}</label>

              <!-- List of Attached Files in Edit Mode -->
              <div v-if="editAttachmentList.length > 0" class="space-y-2">
                <div
                  v-for="(fileUrl, fIdx) in editAttachmentList"
                  :key="fileUrl + fIdx"
                  class="p-2.5 rounded-xl border border-outline-gray-1 bg-surface-gray-2 flex items-center justify-between shadow-2xs"
                >
                  <div class="flex items-center gap-3 overflow-hidden min-w-0">
                    <img
                      v-if="isImageUrl(fileUrl)"
                      :src="fileUrl"
                      class="w-10 h-10 object-cover rounded-lg shrink-0 border border-outline-gray-1 bg-surface-base cursor-pointer"
                      @click="openImagePreview(fileUrl)"
                    />
                    <div v-else class="w-10 h-10 rounded-lg bg-surface-gray-3 border border-outline-gray-1 flex items-center justify-center shrink-0 cursor-pointer" @click="openFileUrl(fileUrl)">
                      <FeatherIcon name="file-text" class="w-5 h-5 text-ink-gray-7" />
                    </div>
                    <div class="min-w-0 cursor-pointer" @click="isImageUrl(fileUrl) ? openImagePreview(fileUrl) : openFileUrl(fileUrl)">
                      <p class="text-xs font-semibold text-ink-gray-9 truncate hover:text-ink-blue-link transition-colors">{{ getFileName(fileUrl) }}</p>
                      <p class="text-[11px] text-ink-gray-5 font-mono truncate">{{ fileUrl }}</p>
                    </div>
                  </div>
                  <Button variant="ghost" icon="lucide-x" class="!p-1 h-auto text-ink-gray-4 hover:!text-ink-red-3 hover:!bg-surface-red-2" @click="removeEditAttachment(fIdx)" />
                </div>
              </div>

              <!-- Upload Drag & Drop Trigger -->
              <div
                class="relative border-2 border-dashed border-outline-gray-2 rounded-xl p-4 text-center hover:border-ink-gray-6 transition-colors cursor-pointer bg-surface-gray-1"
                @click="triggerEditFileInput(field.name)"
              >
                <FormControl
                  type="file"
                  :id="'edit_file_input_' + field.name"
                  class="hidden"
                  multiple
                  accept="*/*"
                  @change="handleEditFileUpload($event, field.name)"
                />
                <div class="flex flex-col items-center gap-1">
                  <FeatherIcon name="paperclip" class="w-6 h-6 text-ink-gray-5" />
                  <span class="text-xs font-semibold text-ink-gray-8">
                    {{ uploadingEditFiles ? 'Uploading files...' : (editAttachmentList.length > 0 ? '+ Add More Files' : 'Click or drag files here to upload') }}
                  </span>
                  <span class="text-[10px] text-ink-gray-5">Supports Images, PDFs, Zip, Documents (Select multiple files)</span>
                </div>
              </div>
            </div>

            <!-- Engine / option picker -->
            <div v-else-if="field.type === 'select'" class="flex items-center justify-between gap-3 text-sm">
              <label class="w-28 shrink-0 text-ink-gray-5 font-normal">{{ field.label }}</label>
              <div class="flex-1 min-w-0">
                <FormControl type="select" v-model="editForm[field.name]" :options="field.options" class="w-full text-sm cursor-pointer" />
              </div>
            </div>

            <!-- Toggle -->
            <div v-else-if="field.type === 'checkbox'" class="flex items-center justify-between gap-3 text-sm">
              <label class="w-28 shrink-0 text-ink-gray-5 font-normal">{{ field.label }}</label>
              <div class="flex-1 min-w-0 flex justify-end">
                <FormControl type="checkbox" v-model="editForm[field.name]" />
              </div>
            </div>

            <!-- Text / Password / URL -->
            <div v-else class="flex items-center justify-between gap-3 text-sm">
              <label class="w-28 shrink-0 text-ink-gray-5 font-normal">{{ field.label }}</label>
              <div class="flex-1 min-w-0 relative">
                <TextInput :type="field.type === 'password' && !editRevealedFields[field.name] ? 'password' : 'text'" v-model="editForm[field.name]" :placeholder="field.placeholder" class="w-full text-sm" :class="[field.mono ? 'font-mono' : '', field.type === 'password' ? 'pr-9' : '']" />
                <Button v-if="field.type === 'password'" variant="ghost" :icon="editRevealedFields[field.name] ? 'lucide-eye-off' : 'lucide-eye'" class="absolute right-1 top-1 !p-1.5 h-auto text-ink-gray-4 hover:text-ink-gray-9 focus:outline-none" @click="toggleField(field.name, true)" />
              </div>
            </div>
          </template>
        </div>

        <!-- Linux inventory and automation access -->
        <div v-if="editForm.secret_type === 'Linux Server'" class="pt-3 border-t border-outline-gray-1 space-y-3">
          <div class="flex items-center justify-between">
            <p class="text-xs font-semibold text-ink-gray-5 uppercase tracking-wider">
              Servers ({{ editForm.linux_hosts.length }})
            </p>
            <Button variant="subtle" size="sm" icon-left="plus" label="Add host"
                    @click="editForm.linux_hosts.push({ hostname: '', ssh_port: '' })" />
          </div>

          <div v-for="(host, hIdx) in editForm.linux_hosts" :key="hIdx" class="flex items-center gap-2">
            <FormControl class="flex-1 text-sm" v-model="host.hostname" placeholder="hostname or IP" />
            <FormControl class="w-20 text-sm" v-model="host.ssh_port" placeholder="22" />
            <Button variant="ghost" icon="lucide-x" class="!p-1 h-auto text-ink-gray-4 hover:!text-ink-red-3"
                    @click="editForm.linux_hosts.splice(hIdx, 1)" />
          </div>

          <FormControl label="Ansible User" v-model="editForm.ansible_user" class="w-full text-sm" />

          <FormControl
            type="textarea" :rows="4" label="SSH Private Key"
            v-model="editForm.ansible_ssh_private_key"
            :placeholder="secretData.has_ansible_ssh_private_key ? 'Leave blank to keep the stored key' : ''"
            class="w-full text-xs font-mono"
          />
          <p v-if="keyFingerprint" class="text-xs font-mono text-ink-gray-6 leading-relaxed break-all">
            <FeatherIcon name="key" class="w-3.5 h-3.5 inline -mt-0.5 mr-1 shrink-0" />
            {{ keyFingerprint.fingerprint }} ({{ keyFingerprint.comment }})
            <span class="text-ink-gray-4">&mdash; check this matches what you installed on the server</span>
          </p>
          <p v-else-if="keyFingerprintError" class="text-xs text-ink-red-3 leading-relaxed">
            {{ keyFingerprintError }}
          </p>

          <div class="grid grid-cols-2 gap-4">
            <FormControl type="checkbox" label="Use sudo (become)" v-model="editForm.ansible_use_become" />
            <FormControl type="checkbox" label="Strict host key checking" v-model="editForm.strict_host_key_checking" />
          </div>
          <FormControl
            v-if="editForm.ansible_use_become"
            label="sudo Password" v-model="editForm.ansible_become_password"
            :type="editRevealedFields.ansible_become_password ? 'text' : 'password'"
            :placeholder="secretData.has_ansible_become_password ? 'Leave blank to keep it' : 'Blank for passwordless sudo'"
            class="w-full text-sm"
          />
          <p class="text-xs text-ink-gray-5 leading-relaxed">
            Every rotation sets the new password on all hosts above. If any host cannot be updated the
            rotation is abandoned and the ones already changed are put back.
          </p>
        </div>

        <!-- Automatic rotation (Password and Database secrets) -->
        <div v-if="ROTATABLE_SECRET_TYPES.includes(editForm.secret_type)" class="pt-3 border-t border-outline-gray-1 space-y-2">
          <FormControl type="checkbox" label="Enable Automatic Rotation" v-model="editForm.enable_rotation" />
          <p class="text-xs text-ink-gray-5 leading-relaxed">
            Generate a new password on a schedule. Everyone with access is notified and can read the new
            value here.
            <template v-if="SYNCED_SECRET_TYPES.includes(editForm.secret_type)">
              Each rotation is also applied to the systems above, so Vault and they never disagree.
            </template>
            <template v-else>
              Updates the stored value only &mdash; you must apply it to the target system yourself.
            </template>
          </p>
          <div v-if="editForm.enable_rotation" class="grid grid-cols-2 gap-4 pt-1">
            <FormControl label="Rotate Every" type="number" min="1" v-model="editForm.rotation_interval" class="w-full text-sm" />
            <FormControl label="Interval Unit" type="select" v-model="editForm.rotation_unit" :options="ROTATION_UNITS" class="w-full text-sm cursor-pointer" />
          </div>

          <template v-if="editForm.enable_rotation">
            <div v-if="secretData.has_zip_passphrase" class="flex items-center justify-between gap-2 pt-1">
              <p class="text-xs text-ink-gray-6">
                <FeatherIcon name="lock" class="w-3.5 h-3.5 inline -mt-0.5 mr-1" />
                Passphrase protection is ON. Leave the field below blank to keep it.
              </p>
              <Button variant="ghost" size="xs" class="text-xs text-ink-red-4 shrink-0" @click="handleRemovePassphrase">
                Remove
              </Button>
            </div>
            <FormControl
              label="Custom Rotation Passphrase (optional)"
              v-model="editForm.zip_passphrase"
              :type="editRevealedFields.zip_passphrase ? 'text' : 'password'"
              :placeholder="secretData.has_zip_passphrase ? 'Leave blank to keep current passphrase' : 'Leave blank to use the shared site passphrase'"
              class="w-full text-sm"
            >
              <template #suffix>
                <Button variant="ghost" :icon="editRevealedFields.zip_passphrase ? 'lucide-eye-off' : 'lucide-eye'" class="!p-1 h-auto text-ink-gray-4 hover:text-ink-gray-9 focus:outline-none" @click="toggleField('zip_passphrase', true)" />
              </template>
            </FormControl>
            <p class="text-xs text-ink-gray-5 leading-relaxed">
              Stored encrypted, the same way as this secret's own password. Used automatically when this
              secret rotates, so its archive opens with your passphrase instead of the shared site one.
            </p>
          </template>

          <!-- Push the rotated password to the live server -->
          <template v-if="editForm.enable_rotation && editForm.secret_type === 'Database'">
            <div class="pt-2 border-t border-outline-gray-1 space-y-2">
              <FormControl
                type="checkbox"
                label="Apply New Password to the Database"
                v-model="editForm.apply_rotation_to_target"
              />
              <p class="text-xs text-ink-gray-5 leading-relaxed">
                Connect to <strong>{{ editForm.database_type || 'the database' }}</strong> on every rotation
                and change the password there too, so Vault and the server stay in sync. If the server cannot
                be updated the rotation is abandoned and the stored password is left untouched.
              </p>

              <template v-if="editForm.apply_rotation_to_target">
                <FormControl
                  label="Rotation Admin Username"
                  v-model="editForm.rotation_admin_username"
                  placeholder="postgres / root"
                  class="w-full text-sm"
                />
                <FormControl
                  label="Rotation Admin Password"
                  v-model="editForm.rotation_admin_password"
                  :type="editRevealedFields.rotation_admin_password ? 'text' : 'password'"
                  :placeholder="secretData.has_rotation_admin_password ? 'Leave blank to keep current password' : ''"
                  class="w-full text-sm"
                >
                  <template #suffix>
                    <Button variant="ghost" :icon="editRevealedFields.rotation_admin_password ? 'lucide-eye-off' : 'lucide-eye'" class="!p-1 h-auto text-ink-gray-4 hover:text-ink-gray-9 focus:outline-none" @click="toggleField('rotation_admin_password', true)" />
                  </template>
                </FormControl>
                <p class="text-xs text-ink-gray-5 leading-relaxed">
                  The privileged account Vault authenticates as to reset the password. Required, because
                  an account that cannot change its own password would only fail unattended. Stored
                  encrypted, and never rotated by Vault. To remove it, untick applying to the database.
                </p>
              </template>
            </div>
          </template>
        </div>

        <!-- Notes input -->
        <div class="pt-2">
          <FormControl type="textarea" label="Notes" v-model="editForm.notes" :rows="3" placeholder="Enter notes..." class="w-full text-sm" />
        </div>

        <!-- Edit Action Buttons -->
        <div class="flex items-center justify-end gap-2 pt-4 border-t border-outline-gray-1">
          <Button variant="outline" size="sm" @click="isEditing = false">Cancel</Button>
          <Button variant="solid" size="sm" @click="handleSave" :loading="updateResource.loading" class="font-semibold shadow-2xs">Save Changes</Button>
        </div>
      </div>

      <!-- READ ONLY VIEW -->
      <div v-else class="space-y-2.5 py-1">
        <p v-if="!canReveal" class="text-xs text-ink-gray-6 leading-relaxed bg-surface-gray-2 border border-outline-gray-1 rounded-lg p-2.5">
          <FeatherIcon name="lock" class="w-3.5 h-3.5 inline -mt-0.5 mr-1" />
          Only this secret's owner and the people it has been shared with can view its values.
          Administering the vault does not grant access to what is stored in it.
        </p>
        <!-- Secret Type -->
        <div class="flex items-center justify-between py-1 text-sm">
          <span class="w-28 shrink-0 text-ink-gray-5 font-normal">Secret Type</span>
          <span class="min-w-0 flex-1 text-right font-medium text-ink-gray-9 truncate">{{ secretData.secret_type }}</span>
        </div>

        <!-- Folder -->
        <div class="flex items-center justify-between py-1 text-sm">
          <span class="w-28 shrink-0 text-ink-gray-5 font-normal">Folder</span>
          <span class="min-w-0 flex-1 text-right font-medium text-ink-gray-9 truncate">
            {{ getFolderName(secretData.folder) || '—' }}
          </span>
        </div>

        <!-- Rotation schedule -->
        <div v-if="secretData.enable_rotation" class="flex items-center justify-between py-1 text-sm">
          <span class="w-28 shrink-0 text-ink-gray-5 font-normal">Rotation</span>
          <span class="min-w-0 flex-1 text-right font-medium text-ink-gray-9 truncate">
            Every {{ secretData.rotation_interval }} {{ (secretData.rotation_unit || 'Days').toLowerCase() }}
            <span v-if="secretData.next_rotation_on" class="text-ink-gray-5 font-normal">
              &middot; next {{ formatRelativeTime(secretData.next_rotation_on) }}
            </span>
          </span>
        </div>

        <div v-if="secretData.enable_rotation && secretData.has_zip_passphrase" class="flex items-center justify-between py-1 text-sm">
          <span class="w-28 shrink-0 text-ink-gray-5 font-normal">Protection</span>
          <span class="min-w-0 flex-1 text-right font-medium text-ink-gray-9 truncate">
            <FeatherIcon name="lock" class="w-3 h-3 inline -mt-0.5 mr-1" />
            Custom archive passphrase
          </span>
        </div>

        <!-- Linux inventory, with the last result per machine -->
        <div v-if="secretData.secret_type === 'Linux Server'" class="pt-2 space-y-2">
          <div class="flex items-center justify-between">
            <span class="text-xs font-semibold text-ink-gray-5 uppercase tracking-wider">
              Servers ({{ (secretData.linux_hosts || []).length }})
            </span>
            <Button
              v-if="canEdit"
              variant="ghost" size="sm" icon-left="lucide-plug" label="Test"
              :loading="linuxTestResource.loading" @click="handleTestLinux"
            />
          </div>

          <div v-for="host in secretData.linux_hosts || []" :key="host.hostname"
               class="flex items-center justify-between gap-2 py-1 text-sm">
            <span class="font-mono text-ink-gray-8 truncate">
              {{ host.hostname }}<span v-if="host.ssh_port && host.ssh_port !== 22" class="text-ink-gray-5">:{{ host.ssh_port }}</span>
            </span>
            <span v-if="host.last_status" class="shrink-0 text-xs font-medium"
                  :class="host.last_status === 'Success' ? 'text-ink-green-3' : 'text-ink-red-3'">
              {{ host.last_status }}
            </span>
            <span v-else class="shrink-0 text-xs text-ink-gray-4">not yet rotated</span>
          </div>

          <p v-for="host in failedHosts" :key="'e-' + host.hostname"
             class="text-xs text-ink-red-3 bg-surface-red-1 border border-outline-red-1 rounded-lg p-2 break-words">
            <span class="font-mono">{{ host.hostname }}</span>: {{ host.last_error }}
          </p>
        </div>

        <!-- Applies straight to the live server -->
        <div v-if="secretData.apply_rotation_to_target" class="flex items-center justify-between py-1 text-sm">
          <span class="w-28 shrink-0 text-ink-gray-5 font-normal">Applies To</span>
          <span class="min-w-0 flex-1 text-right font-medium text-ink-gray-9 truncate">
            <FeatherIcon name="database" class="w-3 h-3 inline -mt-0.5 mr-1" />
            {{ secretData.database_type || 'Database' }} &middot; live server
          </span>
        </div>

        <div v-if="secretData.apply_rotation_to_target && secretData.last_target_apply_status" class="flex items-center justify-between py-1 text-sm">
          <span class="w-28 shrink-0 text-ink-gray-5 font-normal">Last Applied</span>
          <span
            class="min-w-0 flex-1 text-right font-medium truncate"
            :class="secretData.last_target_apply_status === 'Success' ? 'text-ink-green-3' : 'text-ink-red-3'"
          >
            {{ secretData.last_target_apply_status }}
            <span v-if="secretData.last_target_apply_on" class="text-ink-gray-5 font-normal">
              &middot; {{ formatRelativeTime(secretData.last_target_apply_on) }}
            </span>
          </span>
        </div>

        <p
          v-if="secretData.last_target_apply_status === 'Failed' && secretData.last_target_apply_error"
          class="text-xs text-ink-red-3 bg-surface-red-1 border border-outline-red-1 rounded-lg p-2 whitespace-pre-line break-words"
        >
          {{ secretData.last_target_apply_error }}
        </p>

        <div v-if="canEdit && (secretData.enable_rotation || secretData.secret_type === 'Database')" class="flex justify-end gap-2 pt-1">
          <Button
            v-if="secretData.secret_type === 'Database'"
            variant="outline"
            size="sm"
            icon="lucide-plug"
            label="Test Connection"
            :loading="testConnectionResource.loading"
            @click="handleTestConnection"
          />
          <Button v-if="secretData.enable_rotation" variant="outline" size="sm" icon="lucide-refresh-cw" label="Rotate Now" @click="$emit('open-rotate')" />
        </div>


        <!-- Dynamic Fields Array -->
        <template v-for="field in visibleFieldsFor(secretData.secret_type, secretData)" :key="field.name">
          <!-- File Attachment View Mode -->
          <div v-if="field.type === 'file'" class="pt-3 space-y-3">
            <div class="flex items-center justify-between">
              <span class="block text-xs font-semibold text-ink-gray-5 uppercase tracking-wider">{{ field.label }}</span>
              <span v-if="parseAttachments(secretData[field.name]).length > 0" class="text-xs font-medium text-ink-gray-5">
                {{ parseAttachments(secretData[field.name]).length }} {{ parseAttachments(secretData[field.name]).length === 1 ? 'file' : 'files' }}
              </span>
            </div>

            <div v-if="parseAttachments(secretData[field.name]).length > 0" class="space-y-2 max-h-96 overflow-y-auto pr-1">
              <div
                v-for="(fileUrl, aIdx) in parseAttachments(secretData[field.name])"
                :key="fileUrl + aIdx"
                class="bg-surface-gray-2 border border-outline-gray-1 rounded-xl p-3 flex items-center justify-between gap-3 hover:border-outline-gray-2 transition-colors shadow-2xs"
              >
                <div class="flex items-center gap-3 overflow-hidden min-w-0 cursor-pointer" @click="isImageUrl(fileUrl) && !imageLoadErrorMap[fileUrl] ? openImagePreview(fileUrl) : openFileUrl(fileUrl)">
                  <img
                    v-if="isImageUrl(fileUrl) && !imageLoadErrorMap[fileUrl]"
                    :src="fileUrl"
                    class="w-10 h-10 object-cover rounded-lg shrink-0 border border-outline-gray-1 bg-surface-base hover:opacity-90 transition-opacity"
                    @error="imageLoadErrorMap[fileUrl] = true"
                  />
                  <div v-else class="w-10 h-10 rounded-lg bg-surface-gray-3 border border-outline-gray-1 flex items-center justify-center shrink-0">
                    <FeatherIcon name="file-text" class="w-5 h-5 text-ink-gray-7" />
                  </div>
                  <div class="min-w-0">
                    <p class="text-xs font-semibold text-ink-gray-9 truncate hover:text-ink-blue-link transition-colors">{{ getFileName(fileUrl) }}</p>
                    <p class="text-[11px] text-ink-gray-5 font-mono truncate">{{ fileUrl }}</p>
                  </div>
                </div>

                <div class="flex items-center gap-1.5 shrink-0">
                  <Button
                    v-if="isImageUrl(fileUrl) && !imageLoadErrorMap[fileUrl]"
                    variant="subtle"
                    size="xs"
                    icon="eye"
                    label="Preview"
                    class="font-medium text-xs shadow-2xs"
                    @click="openImagePreview(fileUrl)"
                  />

                  <a
                    v-if="canCopy"
                    :href="fileUrl"
                    target="_blank"
                    download
                    class="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-medium bg-surface-base border border-outline-gray-2 text-ink-gray-8 hover:bg-surface-gray-1 transition-colors shadow-2xs"
                  >
                    <FeatherIcon name="download" class="w-3.5 h-3.5 text-ink-gray-6" /> Download
                  </a>
                </div>
              </div>
            </div>

            <div v-else class="text-xs text-ink-gray-4 italic py-1">No files attached.</div>
          </div>

          <div v-else-if="hasFieldValue(field.name)" :class="field.type === 'textarea' ? 'pt-2' : 'flex items-center justify-between py-1 text-sm'">
            <span v-if="field.type === 'textarea'" class="block text-xs font-semibold text-ink-gray-5 uppercase tracking-wider mb-1.5">{{ field.label }}</span>
            <span v-else class="w-28 shrink-0 text-ink-gray-5 font-normal">{{ field.label }}</span>

            <!-- Textarea Content -->
            <div v-if="field.type === 'textarea'" class="relative bg-surface-gray-2 border border-outline-gray-1 rounded-xl p-3 group shadow-inner">
              <pre class="text-xs font-mono text-ink-gray-8 overflow-x-auto max-h-36 whitespace-pre select-all leading-normal">{{ secretData[field.name] }}</pre>
              <Button v-if="canCopy" variant="ghost" :icon="copiedField === field.name ? 'lucide-check' : 'lucide-copy'" :class="copiedField === field.name ? 'text-ink-green-3 hover:text-ink-green-4' : 'text-ink-gray-7'" class="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity bg-surface-base border border-outline-gray-1 shadow-2xs text-xs font-medium h-auto !py-1 !px-2 rounded-md" label="Copy" @click="copyFieldData(field.name)" />
            </div>

            <!-- URL Link -->
            <div v-else-if="field.isLink" class="min-w-0 flex-1 flex items-center justify-end gap-1.5 overflow-hidden">
              <a :href="secretData[field.name]" target="_blank" class="min-w-0 font-medium text-ink-blue-link hover:underline truncate inline-flex items-center justify-end gap-1">
                <span class="truncate">{{ secretData[field.name] }}</span>
                <FeatherIcon name="external-link" class="w-3.5 h-3.5 shrink-0 text-ink-blue-link" />
              </a>
              <Button
                v-if="canCopy"
                variant="ghost"
                :icon="copiedField === field.name ? 'lucide-check' : 'lucide-copy'"
                :class="copiedField === field.name ? 'text-ink-green-3 hover:text-ink-green-4' : 'text-ink-gray-4 hover:text-ink-gray-9'"
                class="!p-1 h-auto focus:outline-none shrink-0"
                :title="'Copy ' + field.label"
                @click="copyFieldData(field.name)"
              />
            </div>

            <!-- Password/Hidden Field -->
            <div v-else-if="field.type === 'password'" class="min-w-0 flex-1 flex items-center justify-end gap-2">
              <span class="font-mono tracking-wider font-medium text-ink-gray-9 truncate">
                {{ revealedFields[field.name] ? decryptedData?.[field.name] : (field.name === 'card_number' ? '•••• •••• •••• ••••' : (field.name === 'card_cvv' ? '•••' : '••••••••••••')) }}
              </span>
              <div v-if="canReveal" class="flex items-center gap-0.5 shrink-0">
                <Button v-if="field.name === 'totp_secret' && secretData.has_totp" variant="subtle" theme="blue" icon="lucide-clock" class="!p-1.5 h-auto text-ink-blue-5 hover:text-ink-blue-6 focus:outline-none" title="Get TOTP Code" @click="$emit('open-totp')" />
                <Button variant="ghost" :icon="revealedFields[field.name] ? 'lucide-eye-off' : 'lucide-eye'" class="!p-1 h-auto text-ink-gray-4 hover:text-ink-gray-9 focus:outline-none" :title="'Reveal ' + field.label" @click="toggleField(field.name)" />
                <Button v-if="canCopy" variant="ghost" :icon="copiedField === field.name ? 'lucide-check' : 'lucide-copy'" :class="copiedField === field.name ? 'text-ink-green-3 hover:text-ink-green-4' : 'text-ink-gray-4 hover:text-ink-gray-9'" class="!p-1 h-auto focus:outline-none" :title="'Copy ' + field.label" @click="copyFieldData(field.name)" />
              </div>
              <FeatherIcon v-else name="lock" class="w-3.5 h-3.5 text-ink-gray-4 shrink-0" title="Not shared with you" />
            </div>

            <!-- Toggle -->
            <div v-else-if="field.type === 'checkbox'" class="min-w-0 flex-1 flex items-center justify-end gap-1.5">
              <span class="font-medium text-ink-gray-9">{{ secretData[field.name] ? 'Yes' : 'No' }}</span>
            </div>

            <!-- Standard Text Field -->
            <div v-else class="min-w-0 flex-1 flex items-center justify-end gap-1.5 overflow-hidden">
              <span class="min-w-0 font-medium text-ink-gray-9 truncate" :class="field.mono ? 'font-mono' : ''">
                {{ field.name === 'db_host' ? secretData.db_host + (secretData.db_port ? ':' + secretData.db_port : '') : secretData[field.name] }}
              </span>
              <Button
                v-if="canCopy"
                variant="ghost"
                :icon="copiedField === field.name ? 'lucide-check' : 'lucide-copy'"
                :class="copiedField === field.name ? 'text-ink-green-3 hover:text-ink-green-4' : 'text-ink-gray-4 hover:text-ink-gray-9'"
                class="!p-1 h-auto focus:outline-none shrink-0"
                :title="'Copy ' + field.label"
                @click="copyFieldData(field.name)"
              />
            </div>
          </div>
        </template>
      </div>
    </div>

    <!-- Image Lightbox Modal / Popover Preview -->
    <Dialog v-model="previewModalOpen" :options="{ size: 'xl', title: 'Image Preview' }">
      <template #body-content>
        <div class="flex flex-col items-center gap-4 py-2">
          <div class="relative w-full max-h-[75vh] flex items-center justify-center bg-surface-gray-7 rounded-2xl overflow-hidden p-2">
            <img :src="previewImageUrl" class="max-w-full max-h-[70vh] object-contain rounded-lg" />
          </div>
          <div class="w-full flex items-center justify-between px-1">
            <span class="text-xs font-mono text-ink-gray-7 truncate max-w-xs">{{ getFileName(previewImageUrl) }}</span>
            <div class="flex items-center gap-2">
              <a :href="previewImageUrl" target="_blank" download class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold bg-surface-base border border-outline-gray-2 text-ink-gray-9 hover:bg-surface-gray-1 transition-colors shadow-2xs">
                <FeatherIcon name="download" class="w-4 h-4 text-ink-gray-7" /> Download
              </a>
              <a :href="previewImageUrl" target="_blank" class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold bg-surface-base border border-outline-gray-2 text-ink-gray-9 hover:bg-surface-gray-1 transition-colors shadow-2xs">
                <FeatherIcon name="external-link" class="w-4 h-4 text-ink-gray-7" /> Open Original
              </a>
            </div>
          </div>
        </div>
      </template>
    </Dialog>
  </article>
</template>

<script setup>
import { ref, reactive, computed, watch } from 'vue'
import {
  Button,
  FeatherIcon,
  TextInput,
  FormControl,
  Dialog,
  toast,
} from 'frappe-ui'

import { useClipboard } from '../composables/clipboard'
import {
  useDecryptSecret,
  useUpdateSecret,
  useFolders,
  useClearZipPassphrase,
  useTestDbConnection,
  useTestLinuxConnection,
  useFingerprintSshKey,
} from '../composables/vault'
import { secretTypeOptions, ROTATION_UNITS, ROTATABLE_SECRET_TYPES, SYNCED_SECRET_TYPES, DATABASE_DEFAULT_PORTS, formatRelativeTime } from '../composables/constants'
import { cleanUrl, parseAttachments, isImageUrl, getFileName } from '../utils/attachments'
import { validateTotpSecret } from '../utils/secretForm'

const props = defineProps({
  name: { type: String, required: true },
  secretData: { type: Object, default: () => ({}) },
  canEdit: { type: Boolean, default: false },
  canCopy: { type: Boolean, default: false },
  // Whether this user may decrypt the stored values at all. Distinct from
  // canCopy/canEdit: an administrator can manage a secret they may not read.
  canReveal: { type: Boolean, default: false },
})

const emit = defineEmits(['open-totp', 'open-rotate', 'saved'])

const detailsOpen = ref(true)
const isEditing = ref(false)

const decryptResource = useDecryptSecret()
const updateResource = useUpdateSecret()
const clearPassphraseResource = useClearZipPassphrase()
const testConnectionResource = useTestDbConnection()
const linuxTestResource = useTestLinuxConnection()

// Identifies whatever is pasted into the SSH key field so it can be checked
// against what was actually installed on the server, before Test Connection
// (or worse, a live rotation) ever runs on the wrong credential.
const fingerprintResource = useFingerprintSshKey()
const keyFingerprint = ref(null)
const keyFingerprintError = ref('')
let fingerprintTimer = null

watch(() => editForm.ansible_ssh_private_key, (key) => {
  keyFingerprint.value = null
  keyFingerprintError.value = ''
  clearTimeout(fingerprintTimer)
  if (!key || !key.trim()) return

  fingerprintTimer = setTimeout(async () => {
    try {
      keyFingerprint.value = await fingerprintResource.submit({ ssh_private_key: key })
    } catch (err) {
      keyFingerprintError.value = err.messages?.[0] || err.message || 'Could not read this key'
    }
  }, 500)
})

// Only hosts whose last run actually failed carry an error worth showing.
const failedHosts = computed(
  () => (props.secretData?.linux_hosts || []).filter(h => h.last_status === 'Failed' && h.last_error)
)

async function handleTestLinux() {
  try {
    const result = await linuxTestResource.submit({ name: props.name })
    if (result.success) toast.success(result.message || 'All hosts reachable')
    else toast.error(result.message || 'Some hosts could not be reached')
    emit('saved')
  } catch (err) {
    toast.error(err.messages?.[0] || err.message || 'Could not reach these hosts')
  }
}
const folders = useFolders()
const clipboard = useClipboard()

folders.submit()

const folderOptions = computed(() => {
  const options = [{ label: 'No Folder', value: '' }]
  if (folders.data) {
    folders.data.forEach(f => {
      if (f.can_write || f.name === props.secretData?.folder) {
        options.push({ label: f.folder_name, value: f.name })
      }
    })
  }
  return options
})

function getFolderName(folderId) {
  if (!folderId) return ''
  const found = folders.data?.find(f => f.name === folderId)
  return found ? found.folder_name : folderId
}

import { visibleFieldsFor } from '../composables/secretFields'

const copiedField = ref(null)
const revealedFields = ref({})
const editRevealedFields = ref({})

const editForm = reactive({
  title: '',
  secret_type: 'Password',
  folder: '',
  url: '',
  username: '',
  email: '',
  notes: '',
  password: '',
  totp_secret: '',
  api_key: '',
  api_secret: '',
  card_holder: '',
  card_number: '',
  card_expiry: '',
  card_cvv: '',
  database_type: '',
  db_host: '',
  db_port: '',
  db_name: '',
  db_auth_source: '',
  db_use_ssl: 0,
  db_password: '',
  ssh_private_key: '',
  attachment: '',
  enable_rotation: 0,
  rotation_interval: 90,
  rotation_unit: 'Days',
  zip_passphrase: '',
  apply_rotation_to_target: 0,
  rotation_admin_username: '',
  rotation_admin_password: '',
  linux_hosts: [],
  ansible_user: '',
  ansible_ssh_private_key: '',
  ansible_become_password: '',
  ansible_use_become: 1,
  strict_host_key_checking: 1,
  ssh_port: 22,
})

const decryptedData = computed(() => decryptResource.data?.decrypted)

watch(() => props.name, (n) => {
  if (n) {
    revealedFields.value = {}
    editRevealedFields.value = {}
    isEditing.value = false
  }
})

function hasFieldValue(fieldName) {
  if (!props.secretData) return false
  if (decryptedData.value && decryptedData.value[fieldName] !== undefined) {
    return Boolean(decryptedData.value[fieldName])
  }
  const hasKey = 'has_' + fieldName.replace('totp_secret', 'totp')
  if (props.secretData[hasKey] !== undefined) {
    return Boolean(props.secretData[hasKey])
  }
  return Boolean(props.secretData[fieldName])
}

function copyField(value, fieldName) {
  if (!value) return
  clipboard.copy(value)
  copiedField.value = fieldName
  setTimeout(() => {
    if (copiedField.value === fieldName) {
      copiedField.value = null
    }
  }, 3000)
}

async function ensureDecrypted(actionCallback) {
  try {
    if (!decryptedData.value) {
      await decryptResource.submit({ name: props.name })
    }
    if (actionCallback) {
      await actionCallback()
    }
  } catch (err) {
    const errMsg = err.messages?.[0] || err.message || 'Failed to decrypt secret'
    toast.error(errMsg)
  }
}

async function toggleField(fieldName, isEdit = false) {
  if (isEdit) {
    editRevealedFields.value[fieldName] = !editRevealedFields.value[fieldName]
    return
  }
  if (revealedFields.value[fieldName]) {
    revealedFields.value[fieldName] = false
    return
  }
  await ensureDecrypted(() => {
    revealedFields.value[fieldName] = true
  })
}

async function copyFieldData(fieldName) {
  let val = decryptedData.value?.[fieldName] || props.secretData?.[fieldName]
  if (!val && fieldName === 'db_host' && props.secretData?.db_host) {
    val = props.secretData.db_host + (props.secretData.db_port ? ':' + props.secretData.db_port : '')
  }
  if (val) {
    copyField(val, fieldName)
  } else {
    await ensureDecrypted(() => {
      if (decryptedData.value?.[fieldName]) {
        copyField(decryptedData.value[fieldName], fieldName)
      } else {
        toast.error('Field is empty')
      }
    })
  }
}

async function toggleEditMode() {
  if (isEditing.value) {
    isEditing.value = false
    return
  }

  await ensureDecrypted(() => {
    editRevealedFields.value = {}

    const sd = props.secretData || {}
    const dd = decryptedData.value || {}

    editForm.title = sd.title || ''
    editForm.secret_type = sd.secret_type || 'Password'
    editForm.folder = sd.folder || ''
    editForm.url = sd.url || ''
    editForm.username = sd.username || ''
    editForm.email = sd.email || ''
    editForm.notes = sd.notes || ''

    editForm.password = dd.password || ''
    editForm.totp_secret = dd.totp_secret || ''
    editForm.api_key = sd.api_key || ''
    editForm.api_secret = dd.api_secret || ''
    editForm.card_holder = sd.card_holder || ''
    editForm.card_number = dd.card_number || ''
    editForm.card_expiry = sd.card_expiry || ''
    editForm.card_cvv = dd.card_cvv || ''
    editForm.database_type = sd.database_type || ''
    editForm.db_host = sd.db_host || ''
    editForm.db_port = sd.db_port || ''
    editForm.db_name = sd.db_name || ''
    editForm.db_auth_source = sd.db_auth_source || ''
    editForm.db_use_ssl = sd.db_use_ssl ? 1 : 0
    editForm.db_password = dd.db_password || ''
    editForm.ssh_private_key = sd.ssh_private_key || ''
    editForm.enable_rotation = sd.enable_rotation ? 1 : 0
    editForm.rotation_interval = sd.rotation_interval || 90
    editForm.rotation_unit = sd.rotation_unit || 'Days'
    editForm.apply_rotation_to_target = sd.apply_rotation_to_target ? 1 : 0
    editForm.rotation_admin_username = sd.rotation_admin_username || ''
    // Neither is ever returned by the server (both are encrypted) — a blank
    // means "keep whatever is stored", so both always start empty.
    editForm.zip_passphrase = ''
    editForm.rotation_admin_password = ''

    editForm.linux_hosts = (sd.linux_hosts || []).map(h => ({
      hostname: h.hostname || '', ssh_port: h.ssh_port || '',
    }))
    editForm.ansible_user = sd.ansible_user || ''
    editForm.ansible_use_become = sd.ansible_use_become ? 1 : 0
    editForm.strict_host_key_checking = sd.strict_host_key_checking ? 1 : 0
    editForm.ssh_port = sd.ssh_port || 22
    // Never returned by the server; blank means "keep what is stored".
    editForm.ansible_ssh_private_key = ''
    editForm.ansible_become_password = ''

    editAttachmentList.value = parseAttachments(sd.attachment)
    syncEditAttachmentForm()

    isEditing.value = true
  })
}

const editAttachmentList = ref([])
const uploadingEditFiles = ref(false)
const previewModalOpen = ref(false)
const previewImageUrl = ref('')
const imageLoadErrorMap = reactive({})

function openImagePreview(url) {
  previewImageUrl.value = cleanUrl(url)
  previewModalOpen.value = true
}

function openFileUrl(url) {
  const cleaned = cleanUrl(url)
  if (cleaned) window.open(cleaned, '_blank')
}

function removeEditAttachment(index) {
  editAttachmentList.value.splice(index, 1)
  syncEditAttachmentForm()
}

function syncEditAttachmentForm() {
  if (editAttachmentList.value.length === 0) {
    editForm.attachment = ''
  } else if (editAttachmentList.value.length === 1) {
    editForm.attachment = editAttachmentList.value[0]
  } else {
    editForm.attachment = JSON.stringify(editAttachmentList.value)
  }
}

function triggerEditFileInput(fieldname) {
  const el = document.getElementById('edit_file_input_' + fieldname)
  if (el) {
    if (el.tagName === 'INPUT') el.click()
    else {
      const input = el.querySelector('input[type="file"]')
      if (input) input.click()
    }
  }
}

async function handleEditFileUpload(event, fieldname) {
  const files = Array.from(event.target.files || [])
  if (!files.length) return
  uploadingEditFiles.value = true
  try {
    for (const file of files) {
      const formData = new FormData()
      formData.append('file', file)
      formData.append('is_private', 1)
      formData.append('doctype', 'Vault Secret')
      if (props.name) {
        formData.append('docname', props.name)
      }

      const response = await fetch('/api/method/frappe_vault.api.secrets.upload_file', {
        method: 'POST',
        headers: {
          'X-Frappe-CSRF-Token': window.csrf_token || ''
        },
        body: formData
      })
      const data = await response.json()
      if (data.message && data.message.file_url) {
        editAttachmentList.value.push(data.message.file_url)
      }
    }
    syncEditAttachmentForm()
  } catch (err) {
    toast.error(err.message || 'File upload failed')
  } finally {
    uploadingEditFiles.value = false
  }
}

async function handleSave() {
  if (!editForm.title || !editForm.title.trim()) {
    toast.error('Please enter a secret title')
    return
  }

  if (editForm.totp_secret && ['Password', 'API Key'].includes(editForm.secret_type)) {
    const validation = validateTotpSecret(editForm.totp_secret)
    if (!validation.ok) {
      toast.error(validation.message)
      return
    }
  }

  try {
    const payload = {
      title: editForm.title,
      secret_type: editForm.secret_type,
      folder: editForm.folder,
      notes: editForm.notes,
      url: editForm.url,
    }

    if (ROTATABLE_SECRET_TYPES.includes(editForm.secret_type)) {
      payload.enable_rotation = editForm.enable_rotation ? 1 : 0
      if (editForm.enable_rotation) {
        payload.rotation_interval = Number(editForm.rotation_interval) || 90
        payload.rotation_unit = editForm.rotation_unit || 'Days'
        // Blank means "leave whatever's already set (or unset) alone" —
        // only send it when the owner actually typed a new one.
        if (editForm.zip_passphrase) {
          payload.zip_passphrase = editForm.zip_passphrase
        }
      }
    }

    if (editForm.secret_type === 'Password') {
      payload.username = editForm.username
      payload.password = editForm.password
      payload.totp_secret = editForm.totp_secret
      payload.url = editForm.url
    } else if (editForm.secret_type === 'API Key') {
      payload.api_key = editForm.api_key
      payload.api_secret = editForm.api_secret
      payload.totp_secret = editForm.totp_secret
      payload.url = editForm.url
    } else if (editForm.secret_type === 'Credit Card') {
      payload.card_holder = editForm.card_holder
      payload.card_number = editForm.card_number
      payload.card_expiry = editForm.card_expiry
      payload.card_cvv = editForm.card_cvv
    } else if (editForm.secret_type === 'Database') {
      payload.database_type = editForm.database_type
      payload.db_host = editForm.db_host
      payload.db_port = editForm.db_port
      payload.db_name = editForm.db_name
      payload.db_auth_source = editForm.db_auth_source
      payload.db_use_ssl = editForm.db_use_ssl ? 1 : 0
      payload.username = editForm.username
      payload.db_password = editForm.db_password

      const applies = editForm.enable_rotation && editForm.apply_rotation_to_target
      payload.apply_rotation_to_target = applies ? 1 : 0
      // Clearing the username is how the pair gets removed, so it is always
      // sent; the password is only sent when freshly typed (blank = keep).
      // Unticking "apply to database" clears the username, and the controller
      // drops the orphaned password with it — a blank password on its own means
      // "keep what is stored", so it cannot do the clearing.
      payload.rotation_admin_username = applies ? editForm.rotation_admin_username : ''
      if (applies && editForm.rotation_admin_password) {
        payload.rotation_admin_password = editForm.rotation_admin_password
      }
    } else if (editForm.secret_type === 'Linux Server') {
      payload.username = editForm.username
      payload.password = editForm.password
      payload.linux_hosts = editForm.linux_hosts
        .filter(h => (h.hostname || '').trim())
        .map(h => ({ hostname: h.hostname.trim(), ssh_port: Number(h.ssh_port) || 0 }))
      payload.ansible_user = editForm.ansible_user
      payload.ansible_use_become = editForm.ansible_use_become ? 1 : 0
      payload.strict_host_key_checking = editForm.strict_host_key_checking ? 1 : 0
      payload.ssh_port = Number(editForm.ssh_port) || 22
      // Each of these is only sent when freshly typed — blank keeps the stored one.
      if (editForm.ansible_ssh_private_key) payload.ansible_ssh_private_key = editForm.ansible_ssh_private_key
      if (editForm.ansible_become_password) payload.ansible_become_password = editForm.ansible_become_password
    } else if (editForm.secret_type === 'SSH Key') {
      payload.username = editForm.username
      payload.ssh_private_key = editForm.ssh_private_key
    } else if (editForm.secret_type === 'Media') {
      syncEditAttachmentForm()
      payload.attachment = editForm.attachment
    }

    await updateResource.submit({
      name: props.name,
      ...payload,
    })

    isEditing.value = false
    decryptResource.submit({ name: props.name })
    window.dispatchEvent(new CustomEvent('vault-secret-updated', { detail: { name: props.name } }))
    emit('saved')
  } catch (err) {
    if (err.messages?.length) {
      err.messages.forEach(msg => toast.error(msg))
    } else {
      toast.error(err.message || 'Failed to save changes')
    }
  }
}

// Choosing an engine fills in its default port and Mongo's auth source, but
// never overwrites something already typed.
watch(() => editForm.database_type, (engine) => {
  if (!engine) return
  if (!editForm.db_port) editForm.db_port = DATABASE_DEFAULT_PORTS[engine] || ''
  if (engine === 'MongoDB' && !editForm.db_auth_source) editForm.db_auth_source = 'admin'
})

async function handleTestConnection() {
  try {
    const result = await testConnectionResource.submit({ name: props.name })
    toast.success(result.message || 'Connection succeeded')
  } catch (err) {
    toast.error(err.messages?.[0] || err.message || 'Could not reach the database')
  }
}

async function handleRemovePassphrase() {
  try {
    await clearPassphraseResource.submit({ name: props.name })
    toast.success('Passphrase protection removed')
    editForm.zip_passphrase = ''
    emit('saved')
  } catch (err) {
    toast.error(err.messages?.[0] || err.message || 'Failed to remove passphrase')
  }
}

defineExpose({ toggleEditMode, isEditing })
</script>
