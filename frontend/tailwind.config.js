// /** @type {import('tailwindcss').Config} */
// export default {
//   content: ['./index.html', './src/**/*.{ts,tsx}'],
//   darkMode: 'class',
//   theme: {
//     extend: {
//       colors: {
//         canvas: 'rgb(var(--canvas) / <alpha-value>)',
//         surface: 'rgb(var(--surface) / <alpha-value>)',
//         elevated: 'rgb(var(--elevated) / <alpha-value>)',
//         border: 'rgb(var(--border) / <alpha-value>)',
//         ink: 'rgb(var(--ink) / <alpha-value>)',
//         muted: 'rgb(var(--muted) / <alpha-value>)',
//         brand: 'rgb(var(--brand) / <alpha-value>)',
//         'brand-fg': 'rgb(var(--brand-fg) / <alpha-value>)',
//         good: 'rgb(var(--good) / <alpha-value>)',
//         warn: 'rgb(var(--warn) / <alpha-value>)',
//         bad: 'rgb(var(--bad) / <alpha-value>)',
//       },
//       fontFamily: {
//         sans: ['Inter', 'ui-sans-serif', 'system-ui', 'Segoe UI', 'Roboto', 'sans-serif'],
//         mono: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'Consolas', 'monospace'],
//       },
//       borderRadius: { xl: '0.75rem', '2xl': '1rem' },
//       boxShadow: {
//         card: '0 1px 2px rgb(0 0 0 / 0.3), 0 8px 24px -12px rgb(0 0 0 / 0.5)',
//         pop: '0 12px 40px -12px rgb(0 0 0 / 0.6)',
//         glow: '0 0 0 1px rgb(var(--brand) / 0.4), 0 0 20px -4px rgb(var(--brand) / 0.5)',
//       },
//       keyframes: {
//         'fade-up': { '0%': { opacity: '0', transform: 'translateY(6px)' }, '100%': { opacity: '1', transform: 'none' } },
//         shimmer: { '100%': { transform: 'translateX(100%)' } },
//         'pulse-ring': { '0%,100%': { opacity: '1' }, '50%': { opacity: '0.4' } },
//         blink: { '0%,100%': { opacity: '1' }, '50%': { opacity: '0' } },
//       },
//       animation: {
//         'fade-up': 'fade-up .22s ease-out',
//         shimmer: 'shimmer 1.4s infinite',
//         'pulse-ring': 'pulse-ring 1.2s ease-in-out infinite',
//         blink: 'blink 1s step-end infinite',
//       },
//     },
//   },
//   plugins: [],
// }
/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        canvas: 'rgb(var(--canvas) / <alpha-value>)',
        surface: 'rgb(var(--surface) / <alpha-value>)',
        elevated: 'rgb(var(--elevated) / <alpha-value>)',
        border: 'rgb(var(--border) / <alpha-value>)',
        ink: 'rgb(var(--ink) / <alpha-value>)',
        muted: 'rgb(var(--muted) / <alpha-value>)',
        brand: 'rgb(var(--brand) / <alpha-value>)',
        'brand-fg': 'rgb(var(--brand-fg) / <alpha-value>)',
        good: 'rgb(var(--good) / <alpha-value>)',
        warn: 'rgb(var(--warn) / <alpha-value>)',
        bad: 'rgb(var(--bad) / <alpha-value>)',
      },
      fontFamily: {
        sans: ['"Skoda Next"', 'Inter', 'ui-sans-serif', 'system-ui', 'Segoe UI', 'Roboto', 'sans-serif'],
        mono: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'Consolas', 'monospace'],
      },
      borderRadius: { xl: '8px', '2xl': '12px' },
      boxShadow: {
        card: '0 1px 3px rgb(0 0 0 / 0.1), 0 10px 30px -12px rgb(0 0 0 / 0.15)',
        pop: '0 12px 40px -12px rgb(0 0 0 / 0.25)',
        glow: '0 0 0 1px rgb(var(--brand) / 0.2), 0 0 20px -4px rgb(var(--brand) / 0.3)',
      },
      keyframes: {
        'fade-up': { '0%': { opacity: '0', transform: 'translateY(6px)' }, '100%': { opacity: '1', transform: 'none' } },
        shimmer: { '100%': { transform: 'translateX(100%)' } },
        'pulse-ring': { '0%,100%': { opacity: '1' }, '50%': { opacity: '0.4' } },
        blink: { '0%,100%': { opacity: '1' }, '50%': { opacity: '0' } },
      },
      animation: {
        'fade-up': 'fade-up .22s ease-out',
        shimmer: 'shimmer 1.4s infinite',
        'pulse-ring': 'pulse-ring 1.2s ease-in-out infinite',
        blink: 'blink 1s step-end infinite',
      },
    },
  },
  plugins: [],
}
