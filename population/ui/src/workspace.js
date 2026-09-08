// The 5 pillars — the workspace navigation, in order (root CLAUDE.md §2). These
// are the "Manage" surface a party opens once it is found in the registry.
export const PILLARS = [
  { id: 'ids',       n: '1', label: 'In-Context IDs',      sub: 'Identities — prefix, GLN, GIAI, GSRN', color: '#2A8F36' },
  { id: 'drivers',   n: '2', label: 'SiLA Drivers',        sub: 'The Rules — what each asset may do',    color: '#1D4ED8' },
  { id: 'workflows', n: '3', label: 'Allotrope Workflows', sub: 'The Events — what each asset does, when', color: '#7C8B12' },
  { id: 'cloud',     n: '4', label: 'Cloud Bindings',      sub: 'Map identities to GCP · Azure · AWS',    color: '#0369A1' },
  { id: 'graph',     n: '5', label: 'AI Graph',            sub: 'Everything connected — friendings, provenance', color: '#7C3AED' },
];

// K-1 ID-type colours (Blueprint K-1 — NORMATIVE, do not change hues without KJ).
export const ID_TYPES = {
  GIAI:  '#2A8F36', CPID: '#1D4ED8', GTIN:  '#D97706', LGTIN: '#7C8B12',
  GLN:   '#7C3AED', GSRN: '#DB2877', GDTI:  '#00A09C',
};

// Pillars the population registry can back with REAL data today. Drivers /
// workflows / cloud bindings are not party rows — they bind AFTER a claim, in the
// engine, so we show them honestly as not-yet-in-registry rather than faking them.
export const LIVE_PILLARS = new Set(['ids', 'graph']);

// Curated, grounded role vocabulary for stamping typed edges on a location (GLN).
// GS1 party-function semantics, kept small and legible for the registration flow.
// The API also accepts a free-text `rel` (advanced) — this is the guided set.
export const ROLE_RELS = [
  { rel: 'ship_from',   label: 'Ships from' },
  { rel: 'ship_to',     label: 'Ships to' },
  { rel: 'bill_to',     label: 'Bill-to' },
  { rel: 'remit_to',    label: 'Remit-to' },
  { rel: 'operated_by', label: 'Operated by' },
  { rel: 'located_at',  label: 'Located at' },
];
const ROLE_REL_SET = new Set(ROLE_RELS.map((r) => r.rel));
export const isRoleRel = (rel) => ROLE_REL_SET.has(rel);
export const roleLabel = (rel) => ROLE_RELS.find((r) => r.rel === rel)?.label || rel;
