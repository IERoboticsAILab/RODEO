/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: ["class"],
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["InterVariable", "Inter", "ui-sans-serif", "system-ui"]
      },
      colors: {
        brand: {
          DEFAULT: "#a6bddb",
          foreground: "#0a0a0a"
        },
        brand2: {
          DEFAULT: "#ece2f0",
          foreground: "#0a0a0a"
        }
      },
      borderRadius: {
        xl: "0.75rem",
        "2xl": "1rem"
      },
      container: {
        center: true,
        padding: "1rem",
        screens: {
          sm: "360px",
          md: "768px",
          lg: "1024px",
          xl: "1200px",
          "2xl": "1440px"
        }
      }
    }
  },
  plugins: [require("@tailwindcss/forms")]
}
