/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        sala: {
          50: '#f0f4ff',
          100: '#e0e8ff',
          200: '#c7d4fe',
          300: '#a3b8fc',
          400: '#7b93f8',
          500: '#5a6ef2',
          600: '#3b82f6',
          700: '#2563eb',
          800: '#1e40af',
          900: '#0f172a',
          950: '#0a0f1e',
        },
      },
    },
  },
  plugins: [],
}
