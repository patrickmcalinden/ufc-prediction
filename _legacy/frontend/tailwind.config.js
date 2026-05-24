/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        ufcred: {
          500: '#D20A11',
          600: '#B0080E',
          700: '#8c060b',
          900: '#520306'
        },
        ufcslate: {
          900: '#111111',
          800: '#1a1a1a',
        }
      },
      fontFamily: {
        sans: ['Inter', 'sans-serif'],
      }
    },
  },
  plugins: [
    require('@tailwindcss/typography'),
  ],
}
