"use client";

import {
  Button,
  Collapse,
  CSSProperties,
  Group,
  Paper,
  Title,
} from "@mantine/core";
import { useState } from "react";
import Pair from "./Pair";

const Chunk = ({
  t,
  j,
  style,
}: {
  t: string;
  j: object;
  style?: CSSProperties;
}) => {
  const [collapsed, setCollapsed] = useState(
    (j as { link: string }).link !== undefined
  );

  const link = (j as { link: string }).link;

  return (
    <Paper withBorder p="md" m="md" style={[styles.container, style]}>
      <Group w="100%" justify="space-between">
        <Title c="blue.5" order={3}>
          {t}
        </Title>
        <Group>
          {link && !link.includes("undefined") && (
            <Button
              component="a"
              href={
                "vscode://file//Users/gusflusser/DxHub/eCR-semantic-interoperability/" +
                link
              }
              size="xs"
            >
              link
            </Button>
          )}
          <Button
            variant="light"
            size="xs"
            onClick={() => setCollapsed(!collapsed)}
          >
            {collapsed ? "expand" : "collapse"}
          </Button>
        </Group>
      </Group>
      <Collapse in={!collapsed} pt="xs">
        {Object.entries(j).map(([key, value]) =>
          value !== null && typeof value === "object" ? (
            <Chunk t={key} j={value} key={key} />
          ) : (
            <Pair k={key} v={value} key={key} />
          )
        )}
      </Collapse>
    </Paper>
  );
};

export default Chunk;

const styles = {
  container: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
  },
};
