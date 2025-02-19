"use client";

import { Button, Collapse, Group, Paper, Title } from "@mantine/core";
import { useState } from "react";
import Pair from "./Pair";

const Chunk = ({ t, j }: { t: string; j: object }) => {
  const [collapsed, setCollapsed] = useState(false);

  return (
    <Paper withBorder p="md" m="md" style={styles.container}>
      <Group w="100%" justify="space-between">
        <Title c="blue.5" order={3}>
          {t}
        </Title>
        <Button
          variant="light"
          size="xs"
          onClick={() => setCollapsed(!collapsed)}
        >
          {collapsed ? "expand" : "collapse"}
        </Button>
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
