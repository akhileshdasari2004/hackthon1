"use client";

import { ThemeProvider as NextThemesProvider } from "next-themes";
import { type FC } from "react";

export const ThemeProvider: FC<{ children: React.ReactNode }> = ({ children }) => (
  <NextThemesProvider attribute="class" defaultTheme="system" enableSystem disableTransitionOnChange={false}>
    {children}
  </NextThemesProvider>
);