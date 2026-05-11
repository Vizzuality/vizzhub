export const ATTENDING_VALUES = ['yes', 'no', 'maybe'] as const;
export type Attending = typeof ATTENDING_VALUES[number];

export const EVENT_TYPES = [
  'Conference', 'Summit', 'Forum', 'Workshop', 'Symposium',
  'Multi-event', 'Networking event', 'Roundtable', 'Training',
  'Webinar', 'Exhibition / Expo', 'Internal event', 'Other',
] as const;
export type EventType = typeof EVENT_TYPES[number];

export const THEMES = [
  'Climate', 'Nature & Biodiversity', 'Oceans & Water',
  'Food & Land Systems', 'Energy & Net Zero', 'Data & Technology',
  'Policy & Finance', 'Social Justice', 'Urban & Cities', 'Other',
] as const;
export type Theme = typeof THEMES[number];

export const REGIONS = [
  'Global', 'Europe', 'North America', 'Latin America & Caribbean',
  'Africa', 'Asia-Pacific', 'Middle East',
] as const;
export type RegionFocus = typeof REGIONS[number];

export const ATTENDEE_ROLES = [
  'Attendee', 'Speaker', 'Panelist', 'Moderator', 'Exhibitor', 'Organizer',
] as const;
export type AttendeeRole = typeof ATTENDEE_ROLES[number];

export interface EventSummary {
  id: string;
  name: string;
  event_type: string;
  theme_primary: string;
  theme_secondary: string | null;
  region_focus: string;
  location_city: string | null;
  location_country: string | null;
  start_date: string;
  end_date: string | null;
  other_costs: number;
  total_cost: number;
  attending: Attending | null;
  rating: number | null;
  url: string | null;
  observations: string | null;
  created_by: string | null;
  attendee_count: number;
  attendee_names: string[];
  created_at: string;
  updated_at: string;
}

export interface Attendee {
  id: string;
  event_id: string;
  user_id: string;
  role: string;
  cost: number | null;
  user_name: string | null;
  user_email: string | null;
  functional_area: string | null;
  created_at: string;
}

export interface EventDetail extends EventSummary {
  attendees: Attendee[];
}

export interface AttendeeUpdate {
  role?: string;
  cost?: number | null;
}

export interface EventCreate {
  name: string;
  event_type: EventType;
  theme_primary: Theme;
  theme_secondary?: Theme | null;
  region_focus: RegionFocus;
  location_city?: string | null;
  location_country?: string | null;
  start_date: string;
  end_date?: string | null;
  other_costs?: number;
  rating?: number | null;
  url?: string | null;
  observations?: string | null;
  attending?: Attending | null;
}

export type EventUpdate = Partial<EventCreate>;

export interface EventListResponse {
  items: EventSummary[];
  total: number;
  page: number;
  page_size: number;
}

export interface EventListParams {
  search?: string;
  year?: number;
  quarter?: number;
  event_type?: string;
  theme_primary?: string;
  region_focus?: string;
  location_country?: string;
  attending?: Attending;
  sort_by?: string;
  sort_dir?: string;
  page?: number;
  page_size?: number;
}

export interface StatGroup {
  label: string;
  count: number;
}

export interface EventStats {
  total_events: number;
  total_attendees: number;
  total_cost: number;
  by_quarter: StatGroup[];
  by_theme: StatGroup[];
  by_type: StatGroup[];
  by_region: StatGroup[];
  by_country: StatGroup[];
  by_role: StatGroup[];
  by_fa: StatGroup[];
}

export interface EventOptions {
  event_types: string[];
  themes: string[];
  regions: string[];
  attendee_roles: string[];
  years_with_data: number[];
}
