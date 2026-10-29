/** @type {import('tailwindcss').Config} */
import frappeUIPreset, { content } from 'frappe-ui/tailwind'

export default {
  presets: [frappeUIPreset],
  content: [
    ...content,
    './index.html',
    './src/**/*.{vue,js,ts,jsx,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          DEFAULT: '#0052ff',
          50: '#eef4ff',
          100: '#d9e5ff',
          200: '#bcd2fe',
          300: '#8eb6fd',
          400: '#5990fb',
          500: '#0052ff',
          600: '#0046e0',
          700: '#0037b3',
          800: '#002e93',
          900: '#062976',
        },
        vault: {
          DEFAULT: '#0052ff',
          50: '#eef4ff',
          100: '#d9e5ff',
          200: '#bcd2fe',
          300: '#8eb6fd',
          400: '#5990fb',
          500: '#0052ff',
          600: '#0046e0',
          700: '#0037b3',
          800: '#002e93',
          900: '#062976',
        },
      },
    },
  },
  plugins: [],
}
