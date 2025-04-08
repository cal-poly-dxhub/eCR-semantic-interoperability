"use client";

import Chunk from "@/components/Chunk";
import { Box, Group, Paper, Stack, Title } from "@mantine/core";
import jsonObject from "../../public/side_by_side.json";

export default function Home() {
  return (
    <Box p="md">
      {jsonObject.map((i, index) => (
        <Paper key={index.toString()} withBorder p="md" m="md">
          <Stack gap="xs">
            <Title c="blue.5" order={3}>
              chunk {index + 1} -- {(i.similarity * 100).toFixed(2)}% similarity
            </Title>
            <Group justify="flex-start" align="flex-start">
              <Chunk
                t="test chunk"
                j={i.test_chunk}
                style={{ maxWidth: "50%" }}
              />
              <Chunk
                t="existing chunk"
                j={i.existing_chunk}
                style={{ maxWidth: "50%" }}
              />
            </Group>
          </Stack>
        </Paper>
      ))}
    </Box>
  );
}
