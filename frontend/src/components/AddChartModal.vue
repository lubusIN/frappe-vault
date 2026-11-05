<template>
  <Dialog
    v-model="show"
    title="Add Chart"
  >
    <template #default>
      <div class="flex flex-col gap-4">
        <FormControl
          v-model="chartType"
          type="select"
          label="Chart Type"
          :options="chartTypes"
        />
        <FormControl
          v-if="chartType === 'number_chart'"
          v-model="numberChart"
          type="select"
          label="Number Chart"
          :options="numberCharts"
        />
        <FormControl
          v-if="chartType === 'axis_chart'"
          v-model="axisChart"
          type="select"
          label="Axis Chart"
          :options="axisCharts"
        />
        <FormControl
          v-if="chartType === 'donut_chart'"
          v-model="donutChart"
          type="select"
          label="Donut Chart"
          :options="donutCharts"
        />
      </div>
    </template>
    <template #actions>
      <div class="flex items-center justify-end gap-2">
        <Button variant="outline" label="Cancel" @click="show = false" />
        <Button variant="solid" label="Add" @click="addChart" />
      </div>
    </template>
  </Dialog>
</template>

<script setup>
import { createResource, Dialog, FormControl, Button } from 'frappe-ui'
import { ref, inject } from 'vue'

const show = defineModel({
  type: Boolean,
  default: false,
})

const items = defineModel('items', {
  type: Array,
  default: () => [],
})

const fromDate = inject('fromDate', ref(''))
const toDate = inject('toDate', ref(''))

function getRandom(len = 4) {
  return Math.random().toString(36).substring(2, 2 + len)
}

const chartType = ref('spacer')
const chartTypes = [
  { label: 'Spacer', value: 'spacer' },
  { label: 'Number Chart', value: 'number_chart' },
  { label: 'Security Score', value: 'security_score' },
  { label: 'Recently Accessed', value: 'recently_accessed' },
  { label: 'Axis Chart (Trends)', value: 'axis_chart' },
  { label: 'Donut Chart (Folders)', value: 'donut_chart' },
]

const numberChart = ref('total_secrets')
const numberCharts = [
  { label: 'Total Secrets', value: 'total_secrets' },
  { label: 'Bookmarks', value: 'bookmarks' },
  { label: 'Active Shares', value: 'active_shares' },
  { label: 'Revoked Shares', value: 'revoked_shares' },
]

const axisChart = ref('vault_trend')
const axisCharts = [
  { label: 'Vault Activity Trend', value: 'vault_trend' },
]

const donutChart = ref('secrets_by_folder')
const donutCharts = [
  { label: 'Secrets by Folder', value: 'secrets_by_folder' },
]

async function addChart() {
  show.value = false
  if (chartType.value === 'spacer') {
    items.value.push({
      name: 'spacer',
      type: 'spacer',
      layout: { x: 0, y: 0, w: 4, h: 2, i: 'spacer_' + getRandom(4) },
    })
  } else if (chartType.value === 'security_score') {
    await getChartByName('security_score', 'security_score', 7, 6)
  } else if (chartType.value === 'recently_accessed') {
    await getChartByName('recently_accessed', 'recently_accessed', 13, 6)
  } else {
    await getChart(chartType.value)
  }
}

async function getChart(type) {
  let name =
    type == 'number_chart'
      ? numberChart.value
      : type == 'axis_chart'
        ? axisChart.value
        : donutChart.value

  let w = 5
  let h = 3
  if (['axis_chart', 'donut_chart'].includes(type)) {
    w = type === 'axis_chart' ? 12 : 8
    h = 8
  }

  await getChartByName(name, type, w, h)
}

async function getChartByName(name, type, width, height) {
  await createResource({
    url: 'frappe_vault.api.dashboard.get_chart',
    params: {
      name,
      type,
      from_date: fromDate.value,
      to_date: toDate.value,
    },
    auto: true,
    onSuccess: (data = {}) => {
      items.value.push({
        name,
        type,
        layout: {
          x: 0,
          y: 0,
          w: width,
          h: height,
          i: name + '_' + getRandom(4),
        },
        data: data,
      })
    },
  })
}
</script>
