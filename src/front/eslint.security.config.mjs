import security from 'eslint-plugin-security';
import typescriptParser from '@typescript-eslint/parser';

export default [
  {
    ignores: [
      '.next/**',
      'node_modules/**',
      'out/**',
      'build/**',
      'dist/**',
      'next-env.d.ts',
    ],
  },
  {
    files: ['**/*.{js,jsx,ts,tsx,mjs,cjs}'],
    plugins: {
      security,
    },
    languageOptions: {
      parser: typescriptParser,
      ecmaVersion: 2020,
      sourceType: 'module',
      parserOptions: {
        ecmaFeatures: {
          jsx: true,
        },
      },
    },
    rules: {
      'security/detect-object-injection': 'warn', // Changed to warn - too many false positives
      'security/detect-child-process': 'error',
      'security/detect-non-literal-fs-filename': 'error',
      'security/detect-non-literal-regexp': 'error',
      'security/detect-unsafe-regex': 'error',
    },
  },
];
