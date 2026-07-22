"use client";

import { ThemeProvider as NextThemeProvider } from "next-themes";

/**
 * Wraps the app so `next-themes` can toggle the `.dark` class on <html>.
 * Dark is the default (the app was dark-only before the toggle existed);
 * the choice persists in localStorage across visits.
 */
export function ThemeProvider({ children }: { children: React.ReactNode }) {
  return (
    <NextThemeProvider
      attribute="class"
      defaultTheme="dark"
      enableSystem={false}
      disableTransitionOnChange
    >
      {children}
    </NextThemeProvider>
  );
}
