import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  define: {
    // The app reads a build-time version constant; tests just need it defined.
    __APP_VERSION__: JSON.stringify('test'),
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'lcov'],
      reportsDirectory: 'coverage',
      include: ['src/**/*.{ts,tsx}'],
      exclude: ['src/**/*.test.{ts,tsx}', 'src/test/**', 'src/main.tsx', 'src/vite-env.d.ts'],
      // Floors set at the currently achieved level so CI catches regressions.
      // Large page components are not yet tested; ratchet these up as that grows.
      thresholds: {
        lines: 12,
        functions: 40,
        branches: 70,
        statements: 12,
      },
    },
  },
})
