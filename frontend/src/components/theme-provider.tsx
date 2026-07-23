"use client";

import { ThemeProvider as NextThemeProvider } from "next-themes";

/**
 * Wraps the app so `next-themes` can toggle the `.dark` class on <html>.
 * Light is the default; the choice persists in localStorage across visits.
 */
export function ThemeProvider({ children }: { children: React.ReactNode }) {
  return (
    <NextThemeProvider
      attribute="class"
      defaultTheme="light"
      enableSystem={false}
      disableTransitionOnChange
    >
      {children}
    </NextThemeProvider>
  );
}
