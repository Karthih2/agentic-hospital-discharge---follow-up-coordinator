import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MotionConfig } from "motion/react";
import type { ReactNode } from "react";
import { BrowserRouter } from "react-router-dom";
import SmoothScroll from "../components/motion/Lenis";
import { AuthProvider } from "../lib/auth";
import { I18nProvider } from "../lib/i18n";

const qc = new QueryClient({ defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } } });

export function Providers({ children }: { children: ReactNode }) {
  return (
    <BrowserRouter>
      <QueryClientProvider client={qc}>
        <I18nProvider>
          <AuthProvider>
            <MotionConfig reducedMotion="user"><SmoothScroll>{children}</SmoothScroll></MotionConfig>
          </AuthProvider>
        </I18nProvider>
      </QueryClientProvider>
    </BrowserRouter>
  );
}
