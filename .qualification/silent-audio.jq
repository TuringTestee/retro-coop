# Combine PipeWire snapshot/update documents without discarding later routing data.
reduce .[][] as $node ({};
  .[$node.id|tostring] = ((.[$node.id|tostring] // {}) * $node))
| [.[] | select(.info != null)]
