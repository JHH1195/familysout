/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./templates/**/*.html",
    "./static/**/*.js"
  ],
  theme: {
    extend: {
      colors: {
        primary: '#3B82F6', // z. B. für Buttons etc.
        secondary: '#F59E0B',
        background: '#F3F4F6',
      },
      fontFamily: {
        sans: ['"Inter"', 'sans-serif'],
      }
    },
  },
  plugins: [],
}
