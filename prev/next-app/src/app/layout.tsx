import "@mantine/core/styles.css";

import { Header } from "@/components/Header";
import { theme } from "@/constants/theme";
import { ColorSchemeScript, MantineProvider, Stack } from "@mantine/core";

export const metadata = {
  title: "DxHub eCR Viewer",
  description: "eCR Viewer",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <ColorSchemeScript />
      </head>
      <body>
        <MantineProvider theme={theme}>
          <Stack h="100vh">
            <Header />
            {children}
          </Stack>
        </MantineProvider>
      </body>
    </html>
  );
}
