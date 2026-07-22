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
      // Floors sit just under the measured level so CI catches regressions.
      // Ratchet these up as coverage grows; Settings.tsx and Dashboard.tsx are
      // the largest gaps and drag the function/branch numbers down.
      thresholds: {
        lines: 75,
        functions: 60,
        branches: 60,
        statements: 72,
      },
    },
  },
})
