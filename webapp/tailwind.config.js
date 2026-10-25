/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        bek: {
          bg: '#111315',
          text: '#F5F2E9',
          accent: '#C7F464',
          accentHover: '#b5e350',
          card: '#1A1D20',
          cardSoft: '#22262B',
          border: '#26292E',
          muted: '#8E95A0',
        },
      },
      fontFamily: {
        sans: ['Plus Jakarta Sans', 'Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      borderRadius: {
        '2xl': '16px',
        '3xl': '24px',
      },
    },
  },
  plugins: [],
};
