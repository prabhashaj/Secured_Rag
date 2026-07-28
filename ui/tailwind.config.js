/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          50: '#f0f7ff',
          100: '#e0effe',
          200: '#bae0fd',
          300: '#7cc8fb',
          400: '#36adfa',
          500: '#0c92eb',
          600: '#0074ca',
          700: '#015da7',
          800: '#064f8a',
          900: '#0b4272',
          950: '#072a4b',
        },
        gold: {
          50: '#fffbeb',
          100: '#fef3c7',
          200: '#fde68a',
          300: '#fcd34d',
          400: '#fbbf24',
          500: '#f59e0b',
          600: '#d97706',
          700: '#b45309',
        },
        surface: {
          bg: '#f8fafc',
          card: '#ffffff',
          input: '#f1f5f9',
          border: '#e2e8f0',
          hover: '#e2e8f0',
        }
      },
      fontFamily: {
        sans: ['Plus Jakarta Sans', 'Inter', '-apple-system', 'BlinkMacSystemFont', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
      borderRadius: {
        'xl': '12px',
        '2xl': '16px',
        '3xl': '24px',
      },
      boxShadow: {
        'soft-sm': '0 2px 8px -2px rgba(15, 23, 42, 0.05)',
        'soft-md': '0 6px 20px -4px rgba(15, 23, 42, 0.08)',
        'soft-lg': '0 12px 32px -6px rgba(15, 23, 42, 0.12)',
        'glow-primary': '0 0 24px -4px rgba(12, 146, 235, 0.25)',
      }
    },
  },
  plugins: [],
}
