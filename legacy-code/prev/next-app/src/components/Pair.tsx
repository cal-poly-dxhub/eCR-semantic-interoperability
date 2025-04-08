import { Group, Text } from "@mantine/core";

const Pair = ({ k, v }: { k: string; v: object }) => {
  return (
    <Group style={styles.container}>
      <Text c="blue.7">{k}</Text>
      <Text>{JSON.stringify(v)}</Text>
    </Group>
  );
};

export default Pair;

const styles = {
  container: {
    flex: 1,
    alignItems: "center",
  },
};
