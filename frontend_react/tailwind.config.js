/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
      },
      colors: {
        // Medical Premium Palette
        medical: {
          900: '#003366', // Deep Blue - Primary brand
          800: '#004080',
          700: '#004d99',
          600: '#0059b3',
          500: '#0066cc',
          400: '#0073e6',
          300: '#3385ff',
          200: '#66a3ff',
          100: '#99c2ff',
          50: '#e6f0ff',
        },
        // Clean White
        white: {
          DEFAULT: '#ffffff',
          50: '#ffffff',
          100: '#f8f9fa',
          200: '#f4f7f6', // Custom grey
          300: '#e9ecef',
          400: '#dee2e6',
          500: '#ced4da',
        },
        // Semantic colors
        success: {
          DEFAULT: '#28a745',
          light: '#34c759',
          dark: '#1e7e34',
        },
        warning: {
          DEFAULT: '#ffc107',
          dark: '#e0a800',
        },
        danger: {
          DEFAULT: '#dc3545',
          light: '#e4606d',
          dark: '#c82333',
        },
        info: {
          DEFAULT: '#17a2b8',
          light: '#38b2ac',
          dark: '#117a8b',
        },
        // Alias para botones y acentos (contraste sobre blanco)
        primary: {
          DEFAULT: '#0059b3',
          dark: '#004d99',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        display: ['Outfit', 'sans-serif'],
      },
      boxShadow: {
        'soft': '0 2px 15px -3px rgba(0, 0, 0, 0.07), 0 10px 20px -2px rgba(0, 0, 0, 0.04)',
        'card': '0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03)',
        'elevated': '0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)',
      },
      borderRadius: {
        'xl': '1rem',
        '2xl': '1.5rem',
        '3xl': '2rem',
      },
      animation: {
        'fade-in': 'fadeIn 0.3s ease-out',
        'slide-in': 'slideIn 0.3s ease-out',
        'pulse-soft': 'pulseSoft 2s ease-in-out infinite',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideIn: {
          '0%': { transform: 'translateX(100%)', opacity: '0' },
          '100%': { transform: 'translateX(0)', opacity: '1' },
        },
        pulseSoft: {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.7' },
        },
      },
    },
  },
  plugins: [],
}
