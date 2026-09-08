// Palette matched (not imported) from the platform's registration UI so the two
// read as one family. State color language: verified green, candidate amber,
// exception red. Brand accent is the platform violet.
export const COLOR = {
  brand: '#7C3AED',
  brandDark: '#6D28D9',
  ink: '#111827',
  body: '#374151',
  muted: '#6B7280',
  faint: '#9CA3AF',
  border: '#E5E7EB',
  surface: '#FFFFFF',
  bg: '#F8FAFC',
};

// One source of truth for how each party state looks. Used by chips and tiles.
export const STATE = {
  verified:  { label: 'Verified',  fg: '#166534', bg: '#DCFCE7', dot: '#16A34A' },
  candidate: { label: 'Candidate', fg: '#92400E', bg: '#FEF3C7', dot: '#D97706' },
  exception: { label: 'Exception', fg: '#991B1B', bg: '#FEE2E2', dot: '#DC2626' },
};

export function stateStyle(state) {
  return STATE[state] || { label: state || '—', fg: COLOR.body, bg: '#F3F4F6', dot: COLOR.faint };
}
