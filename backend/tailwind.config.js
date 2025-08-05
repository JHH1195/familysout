/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./templates/**/*.html",
    "./static/**/*.js"
  ],
  theme: {
    extend: {
      colors: {
        flotti: {
          primary: '#F24405',
          secondary: '#F26849',
          accent: '#F23005',
          highlight: '#F28D8D',
          background: '#E2C9F2',
        },
      },
      fontFamily: {
        
        fredoka: ['Fredoka', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
