/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        award: {
          bg:            '#0D0B09',
          'bg-secondary':'#141108',
          surface:       '#1C1810',
          'surface-2':   '#241E13',
          'surface-3':   '#2E2618',
          border:        '#3D3020',
          'border-gold': '#5A4820',
          gold:          '#D4AF37',
          'gold-light':  '#E2CA78',
          'gold-muted':  '#A88C2A',
          'gold-dim':    '#5A4820',
          cream:         '#F4F0EC',
          'cream-muted': '#C4B49A',
          'cream-dim':   '#7A6A54',
          crimson:       '#E05252',
          'crimson-bg':  '#1A0808',
        },
      },
      fontFamily: {
        serif: ['"Cormorant Garamond"', 'Georgia', 'serif'],
        sans:  ['Inter', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
