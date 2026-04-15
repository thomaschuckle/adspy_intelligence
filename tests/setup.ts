import { vi } from 'vitest'
import '@testing-library/jest-dom';

// Prevent accidental network calls
vi.stubGlobal('fetch', vi.fn())
