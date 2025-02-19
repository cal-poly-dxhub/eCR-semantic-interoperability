import Chunk from "@/components/Chunk";
import { Paper, Title } from "@mantine/core";
import jsonObject from "../../public/json_object.json";

export default function Home() {
  return (
    <Paper m="xl" withBorder p="md" radius="md" mih={200} h="100%">
      <Title c="blue.5" order={2}>
        json_object
      </Title>
      <Chunk t="test title" j={jsonObject} />
    </Paper>
  );
}
