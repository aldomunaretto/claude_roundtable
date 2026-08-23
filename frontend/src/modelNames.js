// Human-friendly display names for Claude model identifiers, e.g.
// "claude-opus-5" -> "Claude Opus 5", "claude-opus-4-1-20250805" -> "Claude Opus 4.1"
const MODEL_ID_RE = /^claude-(?:(\d+(?:-\d+)*)-)?(opus|sonnet|haiku|fable|mythos)(?:-(\d+(?:-\d+)*))?(?:-\d{8})?$/;

export function formatModelName(model) {
  if (!model) return model;

  const match = model.match(MODEL_ID_RE);
  if (!match) return model;

  const [, versionBefore, family, versionAfter] = match;
  const version = (versionBefore || versionAfter || '').replace(/-/g, '.');
  const familyName = family.charAt(0).toUpperCase() + family.slice(1);

  return version ? `Claude ${familyName} ${version}` : `Claude ${familyName}`;
}
