import Chunk from "@/components/Chunk";
import { Button, Paper, Title } from "@mantine/core";
import jsonObject from "../../public/json_object.json";

export default function Home() {
  return (
    <Paper m="xl" withBorder p="md" radius="md" mih={200} h="100%">
      <Title c="blue.5" order={2}>
        json_object
      </Title>
      <Button
        component="a"
        href="vscode://file//Users/gusflusser/DxHub/eCR-semantic-interoperability/assets/florida/86a927d6-9a33-43b7-b3dc-1c57b30a1146_20240726065146.xml"
      >
        link
      </Button>
      <Chunk t="test title" j={jsonObject} />
    </Paper>
  );
}
