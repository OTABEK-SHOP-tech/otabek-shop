/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        bek: {
          bg: '#F8F9FA',
          bgDarker: '#F1F3F5',
          text: '#111827',
          graphite: '#111827',
          accent: '#16A34A',
          accentHover: '#15803D',
          accentLight: '#DCFCE7',
          card: '#FFFFFF',
          cardSoft: '#F3F4F6',
          border: '#E5E7EB',
          borderLight: '#F3F4F6',
          muted: '#6B7280',
          mutedLight: '#9CA3AF',
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
