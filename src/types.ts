/**
 * Required fields for CSV output
 */
export interface DemographicRecord {
  postal_code: string;
  segment_number: string;
  segment_description: string;
  average_household_income: string;
  average_household_net_worth: string;
  home_type: string;
}

/**
 * Raw database row structure
 */
export interface DatabaseRow {
  postal_code: string;
  data: string;
}

/**
 * Complete PRIZM data structure as stored in JSON
 */
export interface PrizmData {
  postal_code: string;
  segment_number?: string;
  segment_name?: string;
  segment_description?: string;
  who_they_are?: string;
  average_household_income?: string;
  education?: string;
  urbanity?: string;
  average_household_net_worth?: string;
  occupation?: string;
  diversity?: string;
  family_life?: string;
  tenure?: string;
  home_type?: string;
  status?: string;
}
