import js from "@eslint/js";
import prettier from "eslint-config-prettier";
import svelte from "eslint-plugin-svelte";
import globals from "globals";
import tseslint from "typescript-eslint";

export default [
  { ignores: ["build/**", ".svelte-kit/**", "node_modules/**"] },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  ...svelte.configs["flat/recommended"],
  { languageOptions: { globals: { ...globals.browser, ...globals.node } } },
  // The desktop app is always mounted at /; outbound ATS links are absolute.
  { rules: { "svelte/no-navigation-without-resolve": "off" } },
  prettier
];
