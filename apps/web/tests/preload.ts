import { mock } from "bun:test";

// `server-only` is a build-time guard for Next.js — inert under bun test.
mock.module("server-only", () => ({}));
