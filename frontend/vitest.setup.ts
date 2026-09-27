// Registers jest-dom matchers against vitest's `expect` and augments the vitest
// `Assertion` types (e.g. toBeInTheDocument), so both runtime and tsc are satisfied.
import '@testing-library/jest-dom/vitest';
