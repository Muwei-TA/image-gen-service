/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        background: '#F5F3FF',
        surface: '#FFFFFF',
        primary: '#6366F1',
        primaryHover: '#4F46E5',
        secondary: '#818CF8',
        cta: '#10B981',
        ctaHover: '#059669',
        text: '#1E1B4B',
      },
      fontFamily: {
        sans: ['"Plus Jakarta Sans"', 'system-ui', 'sans-serif'],
        mono: ['Fira Code', 'monospace'],
      },
    },
  },
  plugins: [],
}
