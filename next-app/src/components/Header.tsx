"use client";

import { Anchor, Box, Group, Text } from "@mantine/core";

export const Header = () => {
  return (
    <Box bg="black.0" h="4rem" pos="sticky" top={0}>
      <header>
        <Group justify="space-between" h="100%" p="md">
          <Anchor href="/" px="md" style={{ textDecoration: "none" }}>
            <Text size="xl" style={{ fontWeight: "bold" }}>
              eCR Viewer
            </Text>
          </Anchor>
          <Group visibleFrom="sm">
            <Group>
              {/* <Button
                variant="light"
                component="a"
                href="/builder/"
                style={{ textDecoration: "none" }}
              >
                SOW Generator
              </Button> */}
            </Group>
          </Group>
        </Group>
      </header>
    </Box>
  );
};
