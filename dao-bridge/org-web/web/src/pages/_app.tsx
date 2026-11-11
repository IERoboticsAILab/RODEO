import type { AppProps } from "next/app";
import { ThemeProvider } from "next-themes";
import "@fontsource-variable/inter";
import "../styles/globals.css";
import { WalletProvider } from "../lib/wallet";

export default function MyApp({ Component, pageProps }: AppProps) {
  return (
    <ThemeProvider attribute="class" defaultTheme="system" enableSystem>
      <WalletProvider>
        <Component {...pageProps} />
      </WalletProvider>
    </ThemeProvider>
  );
}