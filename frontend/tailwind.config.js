/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{vue,ts,js}'],
  darkMode: 'media',
  theme: {
    extend: {
      fontFamily: {
        sans: [
          'system-ui',
          '-apple-system',
          'Segoe UI',
          'PingFang SC',
          'Microsoft YaHei',
          'sans-serif',
        ],
      },
      colors: {
        glass: {
          surface: 'rgba(255,255,255,0.55)',
          'surface-dark': 'rgba(20,20,28,0.55)',
        },
      },
      backdropBlur: {
        xs: '2px',
        glass: '24px',
      },
      boxShadow: {
        glass: '0 4px 30px rgba(0,0,0,0.08), inset 0 1px 0 rgba(255,255,255,0.4)',
        'glass-dark': '0 4px 30px rgba(0,0,0,0.45), inset 0 1px 0 rgba(255,255,255,0.08)',
      },
    },
  },
  plugins: [],
}
